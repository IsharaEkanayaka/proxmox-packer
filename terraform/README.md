# Terraform - Deploy VMs from Packer Template

This Terraform configuration deploys Ubuntu VMs from the Packer template created in the parent directory.

## Prerequisites

1. Template created with Packer (ID: 990)
2. Terraform installed
3. Proxmox API credentials

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Configure Variables

Create `terraform.tfvars` from the example:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
proxmox_api_url          = "https://your-proxmox-host:8006/api2/json"
proxmox_api_token_id     = "your-token-id"
proxmox_api_token_secret = "your-token-secret"

vm_count       = 2
vm_name_prefix = "ubuntu-vm"
```

### 3. Plan and Apply

```bash
# Preview changes
terraform plan

# Create VMs
terraform apply

# Or auto-approve
terraform apply -auto-approve
```

### 4. Get VM Information

```bash
# Show all outputs
terraform output

# Show specific output
terraform output vm_ip_addresses
```

### 5. Destroy VMs

```bash
terraform destroy
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `vm_count` | Number of VMs to create | 1 |
| `vm_name_prefix` | Prefix for VM names | ubuntu-vm |
| `vm_cores` | CPU cores per VM | 2 |
| `vm_memory` | Memory in MB | 2048 |
| `vm_disk_size` | Disk size | 20G |
| `template_id` | Template ID to clone | 990 |
| `target_node` | Proxmox node | pve1 |

## Examples

### Create 3 VMs with custom specs

```bash
terraform apply \
  -var="vm_count=3" \
  -var="vm_cores=4" \
  -var="vm_memory=4096" \
  -var="vm_name_prefix=web-server"
```

### Create a single VM

```bash
terraform apply \
  -var="vm_count=1" \
  -var="vm_name_prefix=database"
```

## File Structure

```
terraform/
├── versions.tf          # Terraform and provider versions
├── providers.tf         # Proxmox provider configuration
├── variables.tf         # Variable definitions
├── main.tf             # VM resource definitions
├── outputs.tf          # Output definitions
├── terraform.tfvars.example  # Example variables file
└── README.md           # This file
```

## Notes

- VMs are created as full clones of the template
- DHCP is configured by default
- QEMU guest agent is enabled
- SSH keys can be added via the `sshkeys` parameter in main.tf
