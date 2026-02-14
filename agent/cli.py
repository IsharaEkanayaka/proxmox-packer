"""CLI entry point for the Proxmox K8s Agent."""

from __future__ import annotations

import argparse
import os
import sys

from .models import ClusterSpec
from .intent_parser_llm import parse_intent, explain_interpretation
from .llm import OllamaConfig, OllamaError
from .proxmox_client import ProxmoxConfig, ProxmoxClient
from .config_generator import write_configs
from .orchestrator import run_pipeline, print_results


BANNER = r"""
  ____                                          _  _____      
 |  _ \ _ __ _____  ___ __ ___   _____  __    | |/ ( _ ) ___ 
 | |_) | '__/ _ \ \/ / '_ ` _ \ / _ \ \/ /____| ' // _ \/ __|
 |  __/| | | (_) >  <| | | | | | (_) >  <|____| . \ (_) \__ \
 |_|   |_|  \___/_/\_\_| |_| |_|\___/_/\_\    |_|\_\___/|___/
                                                               
          Intent-Driven Kubernetes Provisioning Agent
"""


def cmd_create(args):
    """Handle the 'create' subcommand."""
    intent = " ".join(args.intent) if args.intent else None

    if not intent:
        # Interactive mode
        print(BANNER)
        print("Describe the Kubernetes cluster you need:\n")
        print("  Examples:")
        print('    "production cluster with 5 workers and monitoring"')
        print('    "dev cluster for testing, 4gb memory"')
        print('    "ML training cluster with 8 cores, 16gb RAM, 3 workers"')
        print('    "lightweight single node for learning"')
        print()
        intent = input("Your intent: ").strip()
        if not intent:
            print("No intent provided. Exiting.")
            sys.exit(1)

    # Build Ollama config from args
    ollama_config = _build_ollama_config(args)

    # Discover Proxmox resources for context-aware planning
    proxmox_context = _discover_proxmox(args)

    # Parse intent via LLM
    try:
        spec = parse_intent(intent, ollama_config, proxmox_context)
    except OllamaError as e:
        print(f"\n  Error: {e}")
        sys.exit(1)

    # Show interpretation
    print()
    print(explain_interpretation(intent, spec))
    print()

    if not args.yes:
        confirm = input("Proceed with this configuration? [y/N/edit]: ").strip().lower()
        if confirm == "edit":
            spec = _interactive_edit(spec)
            print()
            print(spec.summary())
            print()
            confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Gather Proxmox credentials
    proxmox_creds = _gather_credentials(args)

    # Generate configs
    print("\nGenerating configuration files...")
    files = write_configs(spec, proxmox_creds, dry_run=args.dry_run)
    for path in files:
        print(f"  {'[DRY RUN] ' if args.dry_run else ''}Written: {path}")

    # Run pipeline
    if args.apply:
        print("\nStarting provisioning pipeline...")
        results = run_pipeline(
            spec,
            skip_packer=args.skip_packer,
            auto_approve=args.yes,
            dry_run=args.dry_run,
        )
        print_results(results)
    else:
        print("\nConfiguration files generated. To provision the cluster:")
        print("  1. cd terraform && terraform init && terraform apply")
        print("  2. Wait for VMs to boot (~60s)")
        print("  3. cd ../ansible && ansible-playbook -i inventory.ini site.yml")
        if spec.addons:
            print("  4. ansible-playbook -i inventory.ini addons.yml")
        print()
        print("Or run again with --apply to execute the full pipeline automatically.")


def cmd_preview(args):
    """Handle the 'preview' subcommand."""
    intent = " ".join(args.intent)
    if not intent:
        print("Please provide an intent to preview.")
        sys.exit(1)

    ollama_config = _build_ollama_config(args)

    # Discover Proxmox resources for context-aware planning
    proxmox_context = _discover_proxmox(args)

    try:
        spec = parse_intent(intent, ollama_config, proxmox_context)
    except OllamaError as e:
        print(f"\n  Error: {e}")
        sys.exit(1)
    print(explain_interpretation(intent, spec))
    print()

    # Show generated files preview
    files = write_configs(spec, dry_run=True)
    for path, content in files.items():
        print(f"\n{'─'*60}")
        print(f"  {path}")
        print(f"{'─'*60}")
        print(content)


def _interactive_edit(spec: ClusterSpec) -> ClusterSpec:
    """Allow the user to interactively tweak the spec."""
    print("\nEdit cluster spec (press Enter to keep current value):\n")

    val = input(f"  Cluster name [{spec.name}]: ").strip()
    if val:
        spec.name = val
        spec.vm_name_prefix = f"{val}-node"

    val = input(f"  Workers [{spec.worker_count}]: ").strip()
    if val:
        spec.worker_count = int(val)

    val = input(f"  Control planes [{spec.control_plane_count}]: ").strip()
    if val:
        spec.control_plane_count = int(val)

    val = input(f"  Worker cores [{spec.worker_spec.cores}]: ").strip()
    if val:
        spec.worker_spec.cores = int(val)

    val = input(f"  Worker memory MB [{spec.worker_spec.memory_mb}]: ").strip()
    if val:
        spec.worker_spec.memory_mb = int(val)

    val = input(f"  CP cores [{spec.control_plane_spec.cores}]: ").strip()
    if val:
        spec.control_plane_spec.cores = int(val)

    val = input(f"  CP memory MB [{spec.control_plane_spec.memory_mb}]: ").strip()
    if val:
        spec.control_plane_spec.memory_mb = int(val)

    val = input(f"  CNI [{spec.cni_plugin}]: ").strip()
    if val:
        spec.cni_plugin = val

    val = input(f"  K8s version [{spec.k8s_version_minor}]: ").strip()
    if val:
        spec.k8s_version_minor = val

    val = input(f"  IP start [{spec.ip_start}]: ").strip()
    if val:
        spec.ip_start = int(val)

    val = input(f"  Add-ons [{', '.join(spec.addons) or 'none'}]: ").strip()
    if val:
        spec.addons = [a.strip() for a in val.split(",")]

    return spec


def _build_ollama_config(args) -> OllamaConfig:
    """Build OllamaConfig from CLI args and environment."""
    import os
    return OllamaConfig(
        base_url=getattr(args, "ollama_url", None) or os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        model=getattr(args, "model", None) or os.environ.get("OLLAMA_MODEL", "llama3"),
    )


def _gather_credentials(args) -> dict | None:
    """Gather Proxmox API credentials from args or environment."""
    creds = _resolve_proxmox_creds(args)
    if creds:
        return {
            "api_url": creds["api_url"],
            "token_id": creds["token_id"],
            "token_secret": creds["token_secret"],
        }

    # Check if terraform.tfvars already has credentials
    from pathlib import Path
    tfvars = Path(__file__).resolve().parent.parent / "terraform" / "terraform.tfvars"
    if tfvars.exists():
        return None  # Credentials already in file

    print("\n  Proxmox credentials not found in environment or args.")
    print("  Set PROXMOX_API_URL, PROXMOX_API_TOKEN_ID, PROXMOX_API_TOKEN_SECRET")
    print("  or pass --proxmox-url, --proxmox-token-id, --proxmox-token-secret")
    print("  Credentials will be omitted from generated terraform.tfvars.\n")
    return None


def _resolve_proxmox_creds(args) -> dict | None:
    """Resolve Proxmox credentials from CLI args, environment, or terraform.tfvars."""
    api_url = getattr(args, "proxmox_url", None) or os.environ.get("PROXMOX_API_URL")
    token_id = getattr(args, "proxmox_token_id", None) or os.environ.get("PROXMOX_API_TOKEN_ID")
    token_secret = getattr(args, "proxmox_token_secret", None) or os.environ.get("PROXMOX_API_TOKEN_SECRET")

    if api_url and token_id and token_secret:
        return {"api_url": api_url, "token_id": token_id, "token_secret": token_secret}

    # Try extracting from terraform.tfvars
    from pathlib import Path
    import re
    tfvars = Path(__file__).resolve().parent.parent / "terraform" / "terraform.tfvars"
    if tfvars.exists():
        content = tfvars.read_text(encoding="utf-8")
        parsed: dict[str, str] = {}
        for key, var in [("api_url", "proxmox_api_url"),
                         ("token_id", "proxmox_api_token_id"),
                         ("token_secret", "proxmox_api_token_secret")]:
            match = re.search(rf'^{var}\s*=\s*"([^"]*)"', content, re.MULTILINE)
            if match:
                parsed[key] = match.group(1)
        if len(parsed) == 3:
            return parsed

    return None


def _discover_proxmox(args):
    """Attempt to discover Proxmox host resources for LLM context."""
    creds = _resolve_proxmox_creds(args)
    if not creds:
        return None

    config = ProxmoxConfig(
        api_url=creds["api_url"],
        token_id=creds["token_id"],
        token_secret=creds["token_secret"],
        target_node=getattr(args, "target_node", None) or "pve1",
    )
    client = ProxmoxClient(config)

    if not client.is_available():
        print("  Proxmox API not reachable — skipping resource discovery.")
        return None

    print("  Discovering Proxmox resources...")
    ctx = client.discover()
    print(f"  Found: {ctx.resources.cpu_total} cores, "
          f"{ctx.resources.memory_total_mb} MB RAM, "
          f"{len(ctx.existing_vms)} VMs")
    return ctx


def main():
    parser = argparse.ArgumentParser(
        prog="proxmox-k8s-agent",
        description="Intent-driven Kubernetes cluster provisioning on Proxmox",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- create ---
    create_parser = subparsers.add_parser("create", help="Create a cluster from intent")
    create_parser.add_argument("intent", nargs="*", help="Natural language description of the cluster")
    create_parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm without prompting")
    create_parser.add_argument("--apply", action="store_true", help="Run the full provisioning pipeline")
    create_parser.add_argument("--dry-run", action="store_true", help="Preview without writing files or running commands")
    create_parser.add_argument("--skip-packer", action="store_true", default=True, help="Skip Packer template build (default: True)")
    create_parser.add_argument("--build-template", action="store_true", help="Build Packer template before provisioning")
    create_parser.add_argument("--proxmox-url", help="Proxmox API URL")
    create_parser.add_argument("--proxmox-token-id", help="Proxmox API token ID")
    create_parser.add_argument("--proxmox-token-secret", help="Proxmox API token secret")
    create_parser.add_argument("--target-node", default=None, help="Proxmox node name (default: pve1)")
    create_parser.add_argument("--model", default=None, help="Ollama model name (default: llama3)")
    create_parser.add_argument("--ollama-url", default=None, help="Ollama API URL (default: http://localhost:11434)")
    create_parser.set_defaults(func=cmd_create)

    # --- preview ---
    preview_parser = subparsers.add_parser("preview", help="Preview config generation for an intent")
    preview_parser.add_argument("intent", nargs="+", help="Natural language description")
    preview_parser.add_argument("--proxmox-url", help="Proxmox API URL (enables resource discovery)")
    preview_parser.add_argument("--proxmox-token-id", help="Proxmox API token ID")
    preview_parser.add_argument("--proxmox-token-secret", help="Proxmox API token secret")
    preview_parser.add_argument("--target-node", default=None, help="Proxmox node name (default: pve1)")
    preview_parser.add_argument("--model", default=None, help="Ollama model name (default: llama3)")
    preview_parser.add_argument("--ollama-url", default=None, help="Ollama API URL (default: http://localhost:11434)")
    preview_parser.set_defaults(func=cmd_preview)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Handle --build-template flag
    if hasattr(args, "build_template") and args.build_template:
        args.skip_packer = False

    args.func(args)


if __name__ == "__main__":
    main()
