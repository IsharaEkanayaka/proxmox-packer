"""LLM-powered intent parser — sends user intent to Ollama, gets structured JSON back."""

from __future__ import annotations

import json
import re
from .models import ClusterSpec
from .llm import OllamaClient, OllamaConfig, OllamaError
from .proxmox_client import ProxmoxContext


# ---------------------------------------------------------------------------
# System prompt for the LLM
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an infrastructure planning assistant. The user will describe a Kubernetes cluster they need in natural language. Your job is to extract a structured cluster specification from their intent.

You must respond with ONLY a valid JSON object (no markdown, no explanation, no extra text). The JSON must have these fields:

{
  "name": "string — cluster name, e.g. 'k8s-prod'. Infer from context.",
  "worker_count": "integer — number of worker nodes. Must always be provided.",
  "control_plane_count": "integer — number of control plane nodes. Must always be provided.",
  "worker_cores": "integer — CPU cores per worker. Must always be provided.",
  "worker_memory_mb": "integer — RAM in MB per worker. Must always be provided. Convert GB to MB (1GB=1024MB).",
  "cp_cores": "integer — CPU cores per control plane. Must always be provided.",
  "cp_memory_mb": "integer — RAM in MB per control plane. Must always be provided.",
  "ip_start": "integer — starting last-octet for VM IPs (e.g. 201). Must avoid IPs already in use.",
  "cni_plugin": "string — one of: flannel, calico, cilium. Default: flannel.",
  "k8s_version": "string — e.g. '1.31'. Default: '1.31'.",
  "addons": ["list of strings — zero or more of: metrics-server, ingress-nginx, dashboard, prometheus, cert-manager, metallb, longhorn, argocd"],
  "reasoning": "string — one sentence explaining your interpretation of the user's intent, including how you accounted for available resources"
}

Guidelines:
- If the user says "5 nodes" without specifying, assume 1 control plane + 4 workers.
- If the user mentions "monitoring" or "observability", add "prometheus" to addons.
- If the user mentions "ingress" or "load balancing", add "ingress-nginx" to addons.
- If the user mentions "autoscaling" or "HPA", add "metrics-server" to addons.
- If the user mentions "GitOps", add "argocd" to addons.
- If the user mentions "TLS" or "certificates", add "cert-manager" to addons.
- If the user mentions "persistent storage", add "longhorn" to addons.
- For "production", default to higher resources (4 cores, 8GB) and add metrics-server + ingress-nginx.
- For "ML/AI/training", default to high memory workers (8 cores, 16GB).
- For "dev/testing/learning", default to minimal resources (2 cores, 2GB).
- Memory should always be in MB. Convert: 1GB = 1024MB, 4GB = 4096MB, 8GB = 8192MB, 16GB = 16384MB.
- Control planes need at least 2 cores and 2048MB.

Resource-awareness rules (IMPORTANT):
- If you are given information about the Proxmox host's available resources (CPU, memory, storage), you MUST ensure the total requested resources fit within what is available. Leave at least 10%% of host memory free for the hypervisor.
- If the requested cluster would exceed available resources, scale DOWN the per-node specs (fewer cores, less memory) and explain this in the reasoning field.
- If you are given a list of IPs already in use, you MUST choose an ip_start value that avoids ALL of those IPs. For example, if 10.40.19.201-204 are in use, set ip_start to 205.
- If no Proxmox resource information is provided, use sensible defaults and ip_start=201.

Use your own judgement based on the workload type to decide appropriate resources:
- Development/testing/learning: minimal resources (2 cores, 2GB per node)
- Staging/QA: moderate resources (2 cores, 4GB per node)
- Production: higher resources (4 cores, 8GB per node) with metrics-server + ingress-nginx
- ML/AI/training: high memory workers (8 cores, 16GB per worker)
- CI/CD: moderate CPU-heavy workers (4 cores, 4GB per worker)
- High-availability: 3 control planes instead of 1
- Minimal/single-node: 1 control plane, 0 workers

You MUST always return concrete integer values for all fields. Never return null.

Respond with ONLY the JSON object. No markdown code fences. No explanation outside the JSON."""


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def _extract_json_from_response(text: str) -> dict:
    """Extract a JSON object from LLM response, handling markdown fences."""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r'^```\w*\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        text = text.strip()

    # Find the JSON object
    # Look for first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM response:\n{text[:300]}")

    json_str = text[start:end + 1]
    return json.loads(json_str)


def _json_to_spec(data: dict) -> ClusterSpec:
    """Convert the LLM's JSON response into a ClusterSpec."""
    spec = ClusterSpec()

    # 1. Name
    if data.get("name"):
        spec.name = data["name"]
        spec.vm_name_prefix = f"{spec.name}-node"

    # 2. Topology
    spec.worker_count = int(data.get("worker_count", 2))
    spec.control_plane_count = int(data.get("control_plane_count", 1))

    # 3. Worker resources
    spec.worker_spec.cores = int(data.get("worker_cores", 2))
    spec.worker_spec.memory_mb = int(data.get("worker_memory_mb", 2048))

    # 4. Control plane resources (enforce minimums)
    spec.control_plane_spec.cores = max(int(data.get("cp_cores", 2)), 2)
    spec.control_plane_spec.memory_mb = max(int(data.get("cp_memory_mb", 2048)), 2048)

    # 5. IP start (LLM picks it based on used IPs, fallback to 201)
    spec.ip_start = int(data.get("ip_start", 201))

    # 5. CNI
    if data.get("cni_plugin"):
        spec.cni_plugin = data["cni_plugin"]
        if spec.cni_plugin == "calico":
            spec.pod_network_cidr = "192.168.0.0/16"

    # 6. K8s version
    if data.get("k8s_version"):
        spec.k8s_version_minor = data["k8s_version"]
        version_map = {
            "1.31": "1.31.4-1.1",
            "1.30": "1.30.8-1.1",
            "1.29": "1.29.12-1.1",
            "1.28": "1.28.15-1.1",
        }
        spec.k8s_version_full = version_map.get(
            spec.k8s_version_minor, f"{spec.k8s_version_minor}.0-1.1"
        )

    # 7. Add-ons (LLM provides the full list)
    if data.get("addons"):
        spec.addons = list(data["addons"])

    return spec


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_intent(
    text: str,
    ollama_config: OllamaConfig | None = None,
    proxmox_context: ProxmoxContext | None = None,
) -> ClusterSpec:
    """
    Parse natural language intent into a ClusterSpec using Ollama LLM.

    If proxmox_context is provided, the LLM will see real host resources
    and existing VMs so it can size the cluster appropriately and avoid
    IP collisions.

    Raises OllamaError if Ollama is not reachable.
    """
    config = ollama_config or OllamaConfig()
    client = OllamaClient(config)

    if not client.is_available():
        raise OllamaError(
            "Ollama is not running. Start it with: ollama serve\n"
            f"  Expected at: {config.base_url}\n"
            f"  Model needed: {config.model} (pull with: ollama pull {config.model})"
        )

    # Build the user message — optionally prepend Proxmox context
    user_message = text
    if proxmox_context:
        user_message = (
            f"Current Proxmox environment:\n"
            f"{proxmox_context.to_prompt_text()}\n\n"
            f"User request: {text}"
        )
        print(f"  Proxmox context injected ({len(proxmox_context.existing_vms)} existing VMs, "
              f"{len(proxmox_context.used_ips)} IPs in use)")

    print(f"  Sending intent to LLM ({config.model})...")
    response = client.chat(
        messages=[{"role": "user", "content": user_message}],
        system=SYSTEM_PROMPT,
    )

    data = _extract_json_from_response(response)
    spec = _json_to_spec(data)

    # Store the LLM's reasoning for display
    spec._llm_reasoning = data.get("reasoning", "")  # type: ignore[attr-defined]
    spec._llm_raw = data  # type: ignore[attr-defined]

    return spec


def explain_interpretation(text: str, spec: ClusterSpec) -> str:
    """Return a human-readable explanation of how the intent was parsed."""
    reasoning = getattr(spec, "_llm_reasoning", "")

    lines = [
        "Intent interpretation:",
        f'  Input   : "{text}"',
        f"  Engine  : Ollama LLM",
    ]

    if reasoning:
        lines.append(f"  Reasoning: {reasoning}")

    lines.append("")
    lines.append(spec.summary())
    return "\n".join(lines)
