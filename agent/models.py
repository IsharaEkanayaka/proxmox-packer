"""Data models for cluster specification."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class NodeSpec:
    """Hardware specification for a VM node."""
    cores: int = 2
    memory_mb: int = 2048
    disk_size: str = "20G"


@dataclass
class ClusterSpec:
    """Full specification for a Kubernetes cluster."""

    # --- Identity ---
    name: str = "k8s-cluster"
    vm_name_prefix: str = "k8s-node"

    # --- Topology ---
    control_plane_count: int = 1
    worker_count: int = 2
    control_plane_spec: NodeSpec = field(default_factory=lambda: NodeSpec(cores=2, memory_mb=4096))
    worker_spec: NodeSpec = field(default_factory=lambda: NodeSpec(cores=2, memory_mb=2048))

    # --- Kubernetes ---
    k8s_version_minor: str = "1.31"
    k8s_version_full: str = "1.31.4-1.1"
    pod_network_cidr: str = "10.244.0.0/16"
    cni_plugin: str = "flannel"  # flannel | calico | cilium

    # --- Networking ---
    ip_start: int = 201
    ip_prefix: str = "10.40.19."
    ip_gateway: str = "10.40.19.254"
    dns_server: str = "10.40.2.1"
    network_bridge: str = "vmbr0"

    # --- Proxmox ---
    target_node: str = "pve1"
    template_id: int = 990
    storage: str = "local-lvm"

    # --- Add-ons ---
    addons: list[str] = field(default_factory=list)

    # --- Auth (filled from env/secrets) ---
    ssh_user: str = "ubuntu"
    ssh_password: str = "ubuntu"

    @property
    def total_nodes(self) -> int:
        return self.control_plane_count + self.worker_count

    @property
    def control_plane_ips(self) -> list[str]:
        return [
            f"{self.ip_prefix}{self.ip_start + i}"
            for i in range(self.control_plane_count)
        ]

    @property
    def worker_ips(self) -> list[str]:
        offset = self.control_plane_count
        return [
            f"{self.ip_prefix}{self.ip_start + offset + i}"
            for i in range(self.worker_count)
        ]

    @property
    def all_ips(self) -> list[str]:
        return self.control_plane_ips + self.worker_ips

    def summary(self) -> str:
        lines = [
            f"╔══════════════════════════════════════════════════╗",
            f"║  Cluster: {self.name:<39}║",
            f"╠══════════════════════════════════════════════════╣",
            f"║  Control Planes : {self.control_plane_count:<31}║",
            f"║    CPU/Memory   : {self.control_plane_spec.cores} cores / {self.control_plane_spec.memory_mb}MB{' ' * (19 - len(str(self.control_plane_spec.cores)) - len(str(self.control_plane_spec.memory_mb)))}║",
            f"║    IPs          : {', '.join(self.control_plane_ips):<31}║",
            f"║  Workers        : {self.worker_count:<31}║",
            f"║    CPU/Memory   : {self.worker_spec.cores} cores / {self.worker_spec.memory_mb}MB{' ' * (19 - len(str(self.worker_spec.cores)) - len(str(self.worker_spec.memory_mb)))}║",
            f"║    IPs          : {', '.join(self.worker_ips[:3]):<31}║",
        ]
        if len(self.worker_ips) > 3:
            lines.append(f"║                  ... +{len(self.worker_ips) - 3} more{' ' * 22}║")
        lines += [
            f"║  Kubernetes     : v{self.k8s_version_minor:<30}║",
            f"║  CNI            : {self.cni_plugin:<31}║",
            f"║  Add-ons        : {', '.join(self.addons) if self.addons else 'none':<31}║",
            f"║  Proxmox Node   : {self.target_node:<31}║",
            f"╚══════════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)
