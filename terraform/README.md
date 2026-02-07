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

vm_count       = 3
vm_name_prefix = "k8s-node"
vm_cores       = 2
vm_memory      = 2048
```

### 3. Deploy

```bash
terraform plan
terraform apply
```

### 4. Get VM Info

```bash
terraform output
terraform output vm_ip_addresses
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
| `vm_count` | `1` | Number of VMs to create |
| `vm_name_prefix` | `ubuntu-vm` | VM name prefix (produces `prefix-1`, `prefix-2`, ...) |
| `vm_cores` | `2` | CPU cores per VM |
| `vm_memory` | `2048` | Memory in MB per VM |
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

Each VM receives a static IP based on its index:

```
VM 1: {vm_ip_prefix}{vm_ip_start}/24       → 10.40.19.201/24
VM 2: {vm_ip_prefix}{vm_ip_start + 1}/24   → 10.40.19.202/24
VM 3: {vm_ip_prefix}{vm_ip_start + 2}/24   → 10.40.19.203/24
```

IPs are configured via a Proxmox cloud-init drive (`ide2`) and applied by cloud-init on first boot.

## Examples

### Deploy 3 Kubernetes nodes

```bash
terraform apply \
  -var="vm_count=3" \
  -var="vm_name_prefix=k8s-node"
```

### Deploy a high-spec VM

```bash
terraform apply \
  -var="vm_count=1" \
  -var="vm_name_prefix=database" \
  -var="vm_cores=4" \
  -var="vm_memory=8192"
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
