![Packer](https://img.shields.io/badge/packer-FUP-02A8EF?style=for-the-badge&logo=packer&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-VE-E57000?style=for-the-badge&logo=proxmox&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.x-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![Build Status](https://img.shields.io/badge/build-passing-success?style=for-the-badge)

# Proxmox Infrastructure Automation

Complete infrastructure-as-code solution for Proxmox VE using **Packer** (template creation) and **Terraform** (VM provisioning).

Designed for environments behind strict network gateways (e.g., University networks), utilizing **Cloud-Init (NoCloud/CD-ROM)** and **Bastion Hosts** for connectivity.

## 🚀 Features

- **Packer Template Builder:** Fully automated Ubuntu Server 22.04 template creation
- **Terraform VM Provisioning:** Deploy multiple VMs from template with one command
- **Firewall Proof:** Uses local "CIDATA" ISO (CD-ROM method) to inject configuration
- **Network Tunneling:** Works through SSH Bastion/Jump Host (`tesla.ce.pdn.ac.lk`)
- **Cloud-Init Integration:** DHCP networking and automated user provisioning

## 📂 Repository Structure

```
.
├── packer/                      # Template creation with Packer
│   ├── ubuntu-server.pkr.hcl   # Packer configuration
│   ├── credentials.auto.pkrvars.hcl  # Proxmox credentials (gitignored)
│   └── http/                   # Cloud-init files
│       ├── user-data           # Autoinstall configuration
│       └── meta-data           # Metadata for cloud-init
├── terraform/                   # VM provisioning with Terraform
│   ├── versions.tf             # Terraform & provider versions
│   ├── providers.tf            # Proxmox provider configuration
│   ├── variables.tf            # Variable definitions
│   ├── main.tf                 # VM resource definitions
│   ├── outputs.tf              # Output definitions
│   └── terraform.tfvars.example # Example variables file
├── .gitignore
└── README.md                    # This file
```

## 🛠 Prerequisites

### Required Software

1. **HashiCorp Packer** - https://developer.hashicorp.com/packer/downloads
2. **Terraform** >= 1.0 - https://www.terraform.io/downloads
3. **Xorriso** (for ISO generation):
   - **Linux:** `sudo apt install xorriso`
   - **macOS:** `brew install xorriso`
   - **Windows:** Must use **WSL (Windows Subsystem for Linux)**

### Proxmox Requirements

- Proxmox VE cluster with API access
- Ubuntu 22.04 ISO uploaded to Proxmox storage (`local:iso/ubuntu-22.04.5-live-server-amd64.iso`)
- API token with VM creation privileges

---

## 📖 Quick Start Guide

### Part 1: Create Template with Packer

#### 1.1 Configure Credentials

```bash
cd packer
cp credentials.auto.pkrvars.hcl.example credentials.auto.pkrvars.hcl
# Edit with your Proxmox API credentials and bastion password
```

**Example `packer/credentials.auto.pkrvars.hcl`:**
```hcl
proxmox_api_url          = "https://localhost:8006/api2/json"
proxmox_api_token_id     = "your-token-id"
proxmox_api_token_secret = "your-token-secret"
ssh_bastion_username     = "e20094"
ssh_bastion_password     = "your-tesla-password"
```

#### 1.2 Open SSH Tunnel

```bash
# Open tunnel to Proxmox through bastion host
ssh -N -f -L localhost:8006:10.40.18.xx:8006 e20094@tesla.ce.pdn.ac.lk
```
Replace `10.40.18.xx` with your Proxmox node IP.

#### 1.3 Build Template

```bash
packer init .
packer build .
```

**Result:** Template created with ID `990` named `ubuntu-server-template` (~7 minutes)

---

### Part 2: Deploy VMs with Terraform

#### 2.1 Configure Terraform

```bash
cd ../terraform
terraform init
cp terraform.tfvars.example terraform.tfvars
# Edit with your credentials and VM specifications
```

**Example `terraform/terraform.tfvars`:**
```hcl
proxmox_api_url          = "https://localhost:8006"
proxmox_api_token_id     = "your-token-id"
proxmox_api_token_secret = "your-token-secret"

vm_count       = 2
vm_name_prefix = "ubuntu-vm"
vm_cores       = 2
vm_memory      = 2048
```

#### 2.2 Deploy VMs

```bash
terraform plan
terraform apply
```

#### 2.3 Get VM Information

```bash
terraform output
```

**Example output:**
```
vm_ids = [103, 104]
vm_names = ["ubuntu-vm-1", "ubuntu-vm-2"]
vm_ip_addresses = ["10.40.19.57", "10.40.19.58"]
```

---

## 🎯 Usage Examples

### Deploy 3 Web Servers

```bash
cd terraform
terraform apply -var="vm_count=3" -var="vm_name_prefix=web-server"
```

### Create High-Spec Database VM

```bash
terraform apply \
  -var="vm_count=1" \
  -var="vm_name_prefix=database" \
  -var="vm_cores=4" \
  -var="vm_memory=8192"
```

### Destroy All VMs

```bash
terraform destroy
```

---

## 🔐 SSH Access

### Default Credentials

- **Username:** `ubuntu`
- **Password:** `ubuntu`

```bash
ssh ubuntu@<vm-ip-address>
```

### Enable Passwordless SSH

Edit `terraform/main.tf` and add your public key:

```hcl
initialization {
  ip_config {
    ipv4 {
      address = "dhcp"
    }
  }
  user_account {
    username = var.ssh_user
    password = var.ssh_password
    keys     = [
      "ssh-rsa AAAAB3NzaC1yc2E... your-public-key-here"
    ]
  }
}
```

Then run: `terraform apply`

---

## ⚙️ Configuration Details

### Packer Template Specs

- **Template Name:** `ubuntu-server-template`
- **Template ID:** `990`
- **Node:** `pve1`
- **OS:** Ubuntu Server 22.04
- **CPU:** 2 cores
- **Memory:** 2048 MB
- **Disk:** 20GB (raw format on local-lvm)
- **Network:** VirtIO bridge (vmbr0)

- **Cloud-Init:** QEMU guest agent enabled

### Terraform Default Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `vm_count` | 1 | Number of VMs to create |
| `vm_name_prefix` | ubuntu-vm | Prefix for VM names |
| `vm_cores` | 2 | CPU cores per VM |
| `vm_memory` | 2048 | Memory in MB |
| `template_id` | 990 | Template to clone from |
| `target_node` | pve1 | Proxmox node |
| `network_bridge` | vmbr0 | Network bridge |

---

## 🐛 Troubleshooting

### Packer Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| SSH timeout | Network/SSH configuration | 1. Check bastion host connectivity<br>2. Verify cloud-init network config<br>3. Watch Proxmox console for errors |
| CDROM boot error | Boot order conflict | Ensure `boot_iso` type is `ide` and `additional_iso_files` uses different slot |
| No artifact created | SSH tunnel failed | Verify `https://localhost:8006` accessible before build |
| xorriso not found | Missing dependency | Install xorriso (see Prerequisites) |

### Terraform Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Template not found | Wrong template ID/name | Verify template ID 990 exists in Proxmox |
| Provider crash | Using old telmate provider | Ensure using `bpg/proxmox` provider |
| Connection refused | Wrong API URL format | Use `https://host:8006` (not `/api2/json`) |
| Plugin did not respond | Disk configuration conflict | Don't specify disk block when cloning (inherited) |

---

## 🔄 Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   1. PACKER: Build Template                  │
├─────────────────────────────────────────────────────────────┤
│  • Download Ubuntu ISO                                       │
│  • Create VM with autoinstall                                │
│  • Configure with cloud-init (user, packages, networking)    │
│  • Install QEMU guest agent                                  │
│  • Convert to template (ID 990)                              │
│  • Time: ~7 minutes                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                2. TERRAFORM: Deploy VMs                      │
├─────────────────────────────────────────────────────────────┤
│  • Clone from template 990                                   │
│  • Apply cloud-init customization                            │
│  • Assign DHCP IP addresses                                  │
│  • Start VMs                                                 │
│  • Time: ~3 minutes per VM                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Important Notes

- **Credentials:** Never commit `credentials.auto.pkrvars.hcl` or `terraform.tfvars` - they're gitignored
- **SSH Tunnel:** Must be active for both Packer and Terraform operations
- **Template Updates:** Rebuild template with Packer, then redeploy VMs with Terraform
- **Disk Configuration:** VMs inherit 20GB disk from template (resize manually in Proxmox if needed)
- **IP Assignment:** VMs use DHCP by default; IPs visible via `terraform output`

---

## 🤝 Contributing

This project is for educational purposes at the University of Peradeniya. Feel free to fork and adapt for your infrastructure needs.

---

## 📜 License

MIT License - See LICENSE file for details

---

## 🎓 Credits

Developed for the Department of Computer Engineering, University of Peradeniya
