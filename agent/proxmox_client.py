"""Proxmox VE API client — discovers host resources and existing VMs."""

from __future__ import annotations

import json
import ssl
import urllib.request
import urllib.error
from dataclasses import dataclass, field


@dataclass
class ProxmoxConfig:
    """Connection settings for the Proxmox API."""

    api_url: str = ""  # e.g. https://10.40.19.230:8006/api2/json
    token_id: str = ""  # e.g. packer@pam!setup
    token_secret: str = ""
    target_node: str = "pve1"
    verify_ssl: bool = False


@dataclass
class VMInfo:
    """Minimal representation of an existing Proxmox VM."""

    vmid: int
    name: str
    status: str  # running, stopped, etc.
    cores: int = 0
    memory_mb: int = 0
    ips: list[str] = field(default_factory=list)


@dataclass
class NodeResources:
    """Resource summary for a Proxmox node."""

    cpu_total: int = 0  # logical cores
    cpu_used: float = 0.0  # fractional usage (0.0–1.0)
    memory_total_mb: int = 0
    memory_used_mb: int = 0
    storage_total_gb: float = 0.0
    storage_used_gb: float = 0.0


@dataclass
class ProxmoxContext:
    """Full resource context gathered from Proxmox for LLM injection."""

    node_name: str = ""
    resources: NodeResources = field(default_factory=NodeResources)
    existing_vms: list[VMInfo] = field(default_factory=list)
    used_ips: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Format as human-readable text for injection into the LLM prompt."""
        lines = [
            f"=== Proxmox Host Resources (node: {self.node_name}) ===",
            f"  CPU:     {self.resources.cpu_total} cores total, "
            f"~{int(self.resources.cpu_used * self.resources.cpu_total)} in use, "
            f"~{int((1 - self.resources.cpu_used) * self.resources.cpu_total)} available",
            f"  Memory:  {self.resources.memory_total_mb} MB total, "
            f"{self.resources.memory_used_mb} MB used, "
            f"{self.resources.memory_total_mb - self.resources.memory_used_mb} MB available",
            f"  Storage: {self.resources.storage_total_gb:.1f} GB total, "
            f"{self.resources.storage_used_gb:.1f} GB used, "
            f"{self.resources.storage_total_gb - self.resources.storage_used_gb:.1f} GB available",
        ]

        if self.existing_vms:
            lines.append("")
            lines.append("=== Existing VMs ===")
            for vm in self.existing_vms:
                ip_str = ", ".join(vm.ips) if vm.ips else "no IP"
                lines.append(
                    f"  - {vm.name} (VMID {vm.vmid}) — {vm.status}, "
                    f"{vm.cores} cores, {vm.memory_mb} MB, IPs: {ip_str}"
                )
        else:
            lines.append("")
            lines.append("=== No existing VMs found ===")

        if self.used_ips:
            lines.append("")
            lines.append(f"=== IPs already in use: {', '.join(sorted(self.used_ips))} ===")

        return "\n".join(lines)


class ProxmoxClient:
    """Minimal Proxmox REST API client (stdlib only)."""

    def __init__(self, config: ProxmoxConfig):
        self.config = config
        # Derive the base URL (strip trailing /api2/json if present so we can build paths)
        base = config.api_url.rstrip("/")
        if base.endswith("/api2/json"):
            base = base[: -len("/api2/json")]
        self._base = f"{base}/api2/json"

    # ------------------------------------------------------------------
    # Public discovery methods
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if the Proxmox API is reachable with the configured credentials."""
        try:
            self._get("/version")
            return True
        except Exception:
            return False

    def discover(self) -> ProxmoxContext:
        """
        Query Proxmox for node resources + existing VMs and return a ProxmoxContext.
        
        This is the main entry point — gathers everything the LLM needs.
        """
        ctx = ProxmoxContext(node_name=self.config.target_node)

        # 1. Node resources
        try:
            ctx.resources = self._get_node_resources()
        except Exception:
            pass  # Non-fatal: LLM can still work without resource data

        # 2. Existing VMs
        try:
            ctx.existing_vms = self._get_vms()
        except Exception:
            pass

        # 3. Collect all IPs from running/stopped VMs
        for vm in ctx.existing_vms:
            ctx.used_ips.extend(vm.ips)

        return ctx

    # ------------------------------------------------------------------
    # Internal API queries
    # ------------------------------------------------------------------

    def _get_node_resources(self) -> NodeResources:
        """Query /nodes/{node}/status for CPU, memory, storage."""
        data = self._get(f"/nodes/{self.config.target_node}/status")
        status = data.get("data", {})

        cpu_info = status.get("cpuinfo", {})
        memory = status.get("memory", {})
        rootfs = status.get("rootfs", {})

        return NodeResources(
            cpu_total=cpu_info.get("cpus", 0),
            cpu_used=status.get("cpu", 0.0),
            memory_total_mb=memory.get("total", 0) // (1024 * 1024),
            memory_used_mb=memory.get("used", 0) // (1024 * 1024),
            storage_total_gb=rootfs.get("total", 0) / (1024**3),
            storage_used_gb=rootfs.get("used", 0) / (1024**3),
        )

    def _get_vms(self) -> list[VMInfo]:
        """Query /nodes/{node}/qemu for all VMs (excluding templates)."""
        data = self._get(f"/nodes/{self.config.target_node}/qemu")
        vms: list[VMInfo] = []

        for entry in data.get("data", []):
            # Skip templates
            if entry.get("template", 0) == 1:
                continue

            vmid = entry.get("vmid", 0)
            vm = VMInfo(
                vmid=vmid,
                name=entry.get("name", f"vm-{vmid}"),
                status=entry.get("status", "unknown"),
                cores=entry.get("cpus", 0),
                memory_mb=entry.get("maxmem", 0) // (1024 * 1024),
            )

            # Try to get IPs from the QEMU guest agent
            if vm.status == "running":
                try:
                    vm.ips = self._get_vm_ips(vmid)
                except Exception:
                    pass  # Guest agent may not be running

            vms.append(vm)

        return vms

    def _get_vm_ips(self, vmid: int) -> list[str]:
        """Query guest agent for a VM's IP addresses via /qemu/{vmid}/agent/network-get-interfaces."""
        data = self._get(
            f"/nodes/{self.config.target_node}/qemu/{vmid}/agent/network-get-interfaces"
        )
        ips: list[str] = []
        for iface in data.get("data", {}).get("result", []):
            # Skip loopback
            if iface.get("name") == "lo":
                continue
            for addr in iface.get("ip-addresses", []):
                if addr.get("ip-address-type") == "ipv4":
                    ip = addr.get("ip-address", "")
                    if ip and not ip.startswith("127."):
                        ips.append(ip)
        return ips

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _get(self, path: str) -> dict:
        """Make an authenticated GET request to the Proxmox API."""
        url = f"{self._base}{path}"
        headers = {
            "Authorization": f"PVEAPIToken={self.config.token_id}={self.config.token_secret}",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        # Handle self-signed certificates
        ctx = ssl.create_default_context()
        if not self.config.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Proxmox API error {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Cannot reach Proxmox at {url}: {e}") from e
