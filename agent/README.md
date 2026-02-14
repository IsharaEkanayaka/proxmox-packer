# Agent — Intent-Driven Kubernetes Provisioning

The `agent/` module adds **agentic behaviour** to this project: describe the Kubernetes cluster you need in plain English, an LLM (via **Ollama**) interprets your intent, and the agent generates all Terraform + Ansible configuration and optionally runs the full pipeline.

The agent is **resource-aware** — when Proxmox credentials are available, it queries the host for CPU, memory, storage, and existing VMs, then feeds this context to the LLM so it can size the cluster within available capacity and avoid IP collisions.

## Prerequisites

### Ollama (Local LLM)

The agent uses [Ollama](https://ollama.com) to run an LLM locally for intent parsing.

```bash
# Install Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download (Windows)

# Pull a model (recommended: llama3, also works with mistral, gemma2, etc.)
ollama pull llama3

# Start the server (if not already running)
ollama serve
```

Ollama must be running for the agent to work.

## Quick Start

```bash
# From the project root
python -m agent create "production cluster with 5 workers and monitoring"

# Use a specific model
python -m agent create "ML cluster with GPUs" --model mistral

# Point to a remote Ollama instance
python -m agent create "dev cluster" --ollama-url http://my-server:11434
```

The agent will:
1. **Send** your intent to Ollama LLM for interpretation
2. **Show** the interpreted cluster spec (with the LLM's reasoning) for confirmation
3. **Generate** `terraform/terraform.tfvars`, `ansible/inventory.ini`, role defaults, and add-on playbooks
4. **(Optionally) Provision** the cluster end-to-end with `--apply`

## Commands

### `create` — Build a cluster from intent

```bash
# Interactive mode (prompts for intent)
python -m agent create

# One-shot with intent
python -m agent create "ML training cluster with 3 workers, 16GB RAM, 8 cores"

# Auto-confirm + run full pipeline
python -m agent create "dev cluster for testing" --yes --apply

# Dry-run: see what would happen without writing files
python -m agent create "production HA cluster with ingress" --dry-run
```

### `preview` — Preview generated configs

```bash
python -m agent preview "staging cluster with 4 workers and cert-manager"
```

## Intent Examples

| Intent | Result |
|---|---|
| `"dev cluster"` | 1 CP + 1 worker, 2 cores, 2GB |
| `"production cluster with 5 workers"` | 1 CP + 5 workers, 4 cores, 8GB, metrics-server + ingress |
| `"ML training cluster with 16GB RAM"` | 1 CP + 3 workers, 8 cores, 16GB |
| `"CI/CD runner cluster"` | 1 CP + 2 workers, 4 cores, 4GB |
| `"HA cluster with monitoring"` | 3 CP + 3 workers, 4 cores, 8GB, prometheus |
| `"minimal single-node cluster"` | 1 CP + 0 workers, 2 cores, 2GB |
| `"staging with calico and ingress"` | 1 CP + 2 workers, Calico CNI, ingress-nginx |
| `"5 node cluster with 4 cores 8gb"` | 1 CP + 4 workers, 4 cores, 8GB |

## What the LLM Extracts

The LLM interprets your natural language and returns structured JSON with:

- **Topology** — worker/control plane count
- **Resources** — CPU cores, memory per node type
- **IP start** — chosen to avoid IPs already in use on the host
- **CNI plugin** — flannel (default), calico, cilium
- **K8s version** — e.g. 1.31, 1.30
- **Add-ons** — metrics-server, ingress-nginx, dashboard, prometheus, cert-manager, metallb, longhorn, argocd
- **Reasoning** — explains why it chose these settings, including how it accounted for available resources

## Resource-Aware Planning

When Proxmox credentials are available (via env vars, CLI flags, or `terraform.tfvars`), the agent queries the Proxmox API before calling the LLM:

1. **Host resources** — total/used CPU, memory, and storage on the target node
2. **Existing VMs** — names, specs, status, and IP addresses
3. **Used IPs** — all IPv4 addresses assigned to running VMs

This context is injected into the LLM prompt so it can:
- Size the cluster within available capacity (and explain if it had to scale down)
- Pick an `ip_start` that avoids collisions with existing VMs
- Show you exactly what the host looks like before committing

If Proxmox is unreachable, the agent falls back to sensible defaults.

## Generated Files

| File | Purpose |
|---|---|
| `terraform/terraform.tfvars` | VM count, resources, networking |
| `ansible/inventory.ini` | Node IPs, roles, SSH credentials |
| `ansible/roles/common/defaults/main.yml` | K8s version, pod CIDR |
| `ansible/roles/control_plane/defaults/main.yml` | Pod network CIDR |
| `ansible/addons.yml` | Add-on installation playbook (if add-ons requested) |

## Environment Variables

For automated runs, set credentials and LLM config via environment:

```bash
# Proxmox
export PROXMOX_API_URL="https://proxmox:8006/api2/json"
export PROXMOX_API_TOKEN_ID="user@pam!token"
export PROXMOX_API_TOKEN_SECRET="secret-value"

# Ollama (optional, these are the defaults)
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3"
```

Or pass them as CLI flags:
```bash
python -m agent create "dev cluster" --apply \
  --proxmox-url "https://proxmox:8006/api2/json" \
  --proxmox-token-id "user@pam!token" \
  --proxmox-token-secret "secret" \
  --model mistral \
  --ollama-url "http://my-server:11434"
```

## Architecture

```
User Intent (natural language)
        │
        ▼
┌─────────────────┐
│ Proxmox Discovery │  Queries Proxmox API for host
│ (proxmox_client)  │  resources, VMs, and used IPs
└────────┬────────┘
         │ ProxmoxContext
         ▼
┌─────────────────┐
│   Ollama LLM       │  Local LLM (llama3/mistral/etc.)
│   (llm.py)         │  Sees user intent + host context
└────────┬────────┘
         │ JSON
         ▼
┌─────────────────┐
│  Intent Parser     │  JSON → ClusterSpec
│  (intent_parser)   │  Validates and maps LLM output
└────────┬────────┘
         │ ClusterSpec
         ▼
┌─────────────────┐
│  Config Generator  │  Generates terraform.tfvars,
│  (config_gen)      │  inventory.ini, role defaults,
└────────┬────────┘  addons playbook
         │
         ▼
┌─────────────────┐
│   Orchestrator     │  Packer → Terraform → Ansible
│  (orchestrator)    │  Sequential pipeline execution
└─────────────────┘
```
