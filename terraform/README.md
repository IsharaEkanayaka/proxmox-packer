# Terraform — VM Provisioning

Deploys Ubuntu VMs from the Packer template (ID 990) with static IP addresses via cloud-init.

## Prerequisites

1. Template built with Packer (VM ID 990)
2. Terraform >= 1.0
3. Proxmox API credentials

## Quick Start

### 1. Initialize

```bash
cd terraform
terraform init
```

### 2. Configure

Create `terraform.tfvars`:

```hcl
proxmox_api_url          = "https://10.40.19.230:8006/api2/json"
proxmox_api_token_id     = "packer@pam!setup"
proxmox_api_token_secret = "your-token-secret"

control_plane_count = 1
worker_count        = 2
vm_name_prefix      = "k8s-node"

cp_cores      = 2
cp_memory     = 4096
worker_cores  = 2
worker_memory = 2048
```

### 3. Deploy

```bash
terraform plan
terraform apply
```

### 4. Get VM Info

```bash
terraform output
terraform output control_plane_ips
terraform output worker_ips
```

### 5. Destroy

```bash
terraform destroy
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `proxmox_api_url` | — | Proxmox API endpoint |
| `proxmox_api_token_id` | — | API token ID |
| `proxmox_api_token_secret` | — | API token secret |
| `control_plane_count` | `1` | Number of control plane VMs |
| `worker_count` | `2` | Number of worker VMs |
| `vm_name_prefix` | `k8s-node` | VM name prefix (produces `prefix-1`, `prefix-2`, ...) |
| `cp_cores` | `2` | CPU cores per control plane VM |
| `cp_memory` | `4096` | Memory in MB per control plane VM |
| `worker_cores` | `2` | CPU cores per worker VM |
| `worker_memory` | `2048` | Memory in MB per worker VM |
| `vm_ip_prefix` | `10.40.19.` | Network prefix for static IPs |
| `vm_ip_start` | `201` | Starting last octet |
| `vm_ip_gateway` | `10.40.19.254` | Gateway address |
| `vm_dns_server` | `10.40.2.1` | DNS server |
| `vm_storage` | `local-lvm` | Storage pool for cloud-init drive |
| `network_bridge` | `vmbr0` | Network bridge |
| `template_id` | `990` | Template VM ID to clone |
| `target_node` | `pve1` | Proxmox node |
| `ssh_user` | `ubuntu` | VM username |
| `ssh_password` | `ubuntu` | VM password |

## Static IP Assignment

Control plane nodes are provisioned first, then workers:

```
CP 1:     {vm_ip_prefix}{vm_ip_start}/24         → 10.40.19.201/24
Worker 1: {vm_ip_prefix}{vm_ip_start + 1}/24     → 10.40.19.202/24
Worker 2: {vm_ip_prefix}{vm_ip_start + 2}/24     → 10.40.19.203/24
```

IPs are configured via a Proxmox cloud-init drive (`ide2`) and applied by cloud-init on first boot.

## Examples

### Deploy 1 control plane + 3 workers

```bash
terraform apply \
  -var="control_plane_count=1" \
  -var="worker_count=3" \
  -var="vm_name_prefix=k8s-node"
```

### Deploy a high-spec production cluster

```bash
terraform apply \
  -var="control_plane_count=1" \
  -var="worker_count=3" \
  -var="vm_name_prefix=prod" \
  -var="cp_cores=2" \
  -var="cp_memory=4096" \
  -var="worker_cores=4" \
  -var="worker_memory=8192"
```

## File Structure

```
terraform/
├── main.tf                  # VM resource definitions
├── variables.tf             # Variable definitions
├── outputs.tf               # Output definitions (IDs, names, IPs)
├── providers.tf             # Proxmox provider (bpg/proxmox)
├── versions.tf              # Provider version constraints
├── terraform.tfvars         # Your variable values (gitignored)
└── terraform.tfvars.example # Example variable values
```

## Notes

- VMs are full clones of the template
- Disk size (20 GB) is inherited from the template
- QEMU guest agent is enabled for IP reporting
- Cloud-init handles static IP, DNS, gateway, and user configuration
