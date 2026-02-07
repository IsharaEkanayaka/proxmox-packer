![Packer](https://img.shields.io/badge/Packer-1.12-02A8EF?style=for-the-badge&logo=packer&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-VE-E57000?style=for-the-badge&logo=proxmox&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.x-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)

# Proxmox Infrastructure Automation

Infrastructure-as-code for Proxmox VE using **Packer** (template creation) and **Terraform** (VM provisioning) with **static IP assignment** via cloud-init.

## Features

- **Packer Template Builder** — Automated Ubuntu Server 22.04 template with cloud-init support
- **Terraform VM Provisioning** — Deploy multiple VMs with static IPs from a single command
- **Cloud-Init Integration** — Static IP, DNS, and user configuration injected via Proxmox NoCloud drive
- **QEMU Guest Agent** — Enabled by default for IP reporting and VM management

## Repository Structure

```
.
├── packer/
│   ├── ubuntu-server.pkr.hcl          # Packer template configuration
│   ├── credentials.auto.pkrvars.hcl   # Proxmox API credentials (gitignored)
│   └── http/
│       ├── user-data                  # Ubuntu autoinstall configuration
│       └── meta-data                  # Cloud-init metadata
├── terraform/
│   ├── main.tf                        # VM resource definitions
│   ├── variables.tf                   # Variable definitions
│   ├── outputs.tf                     # Output definitions
│   ├── providers.tf                   # Proxmox provider (bpg/proxmox)
│   ├── versions.tf                    # Provider version constraints
│   ├── terraform.tfvars               # Variable values (gitignored)
│   └── terraform.tfvars.example       # Example variable values
└── README.md
```

## Prerequisites

### Software

- [Packer](https://developer.hashicorp.com/packer/downloads) >= 1.10
- [Terraform](https://www.terraform.io/downloads) >= 1.0
- [xorriso](https://www.gnu.org/software/xorriso/) — `sudo apt install xorriso` (Linux)

### Proxmox

- Proxmox VE with API access
- Ubuntu 22.04 ISO uploaded to Proxmox storage (`local:iso/ubuntu-22.04.5-live-server-amd64.iso`)
- API token with VM creation privileges

---

## Quick Start

### 1. Build Template with Packer

```bash
cd packer
```

Create `credentials.auto.pkrvars.hcl`:

```hcl
proxmox_api_url          = "https://10.40.19.230:8006/api2/json"
proxmox_api_token_id     = "packer@pam!setup"
proxmox_api_token_secret = "your-token-secret"
```

Build the template:

```bash
packer init .
packer build .
```

To rebuild an existing template:

```bash
packer build -force .
```

This creates template VM **990** (`ubuntu-server-template`) with cloud-init support. Takes ~10 minutes.

> **Note:** Always use `packer build .` (directory), not `packer build ubuntu-server.pkr.hcl`, so `.auto.pkrvars.hcl` files are auto-loaded.

### 2. Deploy VMs with Terraform

```bash
cd ../terraform
```

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

Deploy:

```bash
terraform init
terraform plan
terraform apply
```

Example output:

```
vm_names        = ["k8s-node-1", "k8s-node-2", "k8s-node-3"]
vm_ip_addresses = ["10.40.19.201", "10.40.19.202", "10.40.19.203"]
```

### 3. Tear Down

```bash
terraform destroy
```

---

## SSH Access

- **Username:** `ubuntu`
- **Password:** `ubuntu`

```bash
ssh ubuntu@10.40.19.201
```

---

## Configuration

### Packer Template Specs

| Setting | Value |
|---------|-------|
| Template ID | 990 |
| Template Name | `ubuntu-server-template` |
| OS | Ubuntu Server 22.04 |
| CPU | 2 cores |
| Memory | 2048 MB |
| Disk | 20 GB (raw, local-lvm) |
| Network | VirtIO on vmbr0 |
| Cloud-Init Drive | ide1 (local-lvm) |
| QEMU Guest Agent | Enabled |

### Terraform Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `vm_count` | `1` | Number of VMs to create |
| `vm_name_prefix` | `ubuntu-vm` | Prefix for VM names (e.g., `k8s-node`) |
| `vm_cores` | `2` | CPU cores per VM |
| `vm_memory` | `2048` | Memory in MB per VM |
| `vm_ip_prefix` | `10.40.19.` | Network prefix for static IPs |
| `vm_ip_start` | `201` | Starting last octet (VMs get .201, .202, ...) |
| `vm_ip_gateway` | `10.40.19.254` | Gateway address |
| `vm_dns_server` | `10.40.2.1` | DNS server |
| `vm_storage` | `local-lvm` | Storage pool for cloud-init drive |
| `network_bridge` | `vmbr0` | Network bridge |
| `template_id` | `990` | Template VM ID to clone |
| `target_node` | `pve1` | Proxmox node |
| `ssh_user` | `ubuntu` | VM username |
| `ssh_password` | `ubuntu` | VM password |

### How Static IPs Work

Terraform passes IP configuration to each VM via a Proxmox cloud-init drive (`ide2`). Each VM gets:

```
IP: {vm_ip_prefix}{vm_ip_start + index}/24
```

For 3 VMs with defaults: `10.40.19.201`, `10.40.19.202`, `10.40.19.203`.

The Packer template is prepared for this by:
1. Attaching a cloud-init drive (`cloud_init = true`)
2. Removing autoinstall's DHCP netplan configs
3. Removing subiquity files that disable cloud-init networking
4. Configuring the NoCloud datasource for Proxmox
5. Cleaning cloud-init state so it re-runs on cloned VMs

---

## Workflow

```
┌──────────────────────────────────────────────────┐
│            1. PACKER: Build Template             │
├──────────────────────────────────────────────────┤
│  Install Ubuntu 22.04 via autoinstall            │
│  Install qemu-guest-agent & openssh-server       │
│  Attach cloud-init drive for Proxmox             │
│  Clean cloud-init state & netplan configs        │
│  Convert to template (ID 990)                    │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│           2. TERRAFORM: Deploy VMs               │
├──────────────────────────────────────────────────┤
│  Full clone from template 990                    │
│  Inject static IP + user config via cloud-init   │
│  Start VMs with assigned IPs                     │
└──────────────────────────────────────────────────┘
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Packer: `username must be specified` | Use `packer build .` (directory) not `packer build file.pkr.hcl` |
| Packer: `VM 990 already exists` | Use `packer build -force .` to overwrite |
| Packer: SSH timeout | Check Proxmox console for autoinstall progress |
| Terraform: VMs get DHCP IPs | Rebuild template — the cloud-init drive or cleanup may be missing |
| Terraform: Template not found | Verify template ID 990 exists in Proxmox |
| Terraform: Connection refused | Use `https://host:8006/api2/json` for API URL |

---

## Important Notes

- **Credentials** — Never commit `credentials.auto.pkrvars.hcl` or `terraform.tfvars`
- **Template updates** — Rebuild with `packer build -force .`, then `terraform destroy && terraform apply`
- **Disk size** — VMs inherit the 20 GB disk from the template
- **IP range** — Default range is `10.40.19.201` to `10.40.19.201 + vm_count - 1`

---

## Credits

Department of Computer Engineering, University of Peradeniya
