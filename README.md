![Packer](https://img.shields.io/badge/Packer-1.12-02A8EF?style=for-the-badge&logo=packer&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-VE-E57000?style=for-the-badge&logo=proxmox&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.x-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)
![Ansible](https://img.shields.io/badge/Ansible-2.x-EE0000?style=for-the-badge&logo=ansible&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.31-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)

# Proxmox Infrastructure Automation

Infrastructure-as-code for Proxmox VE using **Packer** (template creation), **Terraform** (VM provisioning), and **Ansible** (Kubernetes cluster setup) with **static IP assignment** via cloud-init.

## Features

- **Intent-Driven Agent** — Describe the cluster you need in plain English and the agent builds it ([details](agent/README.md))
- **Packer Template Builder** — Automated Ubuntu Server 22.04 template with cloud-init support
- **Terraform VM Provisioning** — Deploy multiple VMs with static IPs from a single command
- **Ansible Kubernetes Setup** — Automated kubeadm cluster with 1 control plane + N workers
- **Cloud-Init Integration** — Static IP, DNS, and user configuration injected via Proxmox NoCloud drive
- **QEMU Guest Agent** — Enabled by default for IP reporting and VM management

## Repository Structure

```
.
├── agent/                                     # Intent-driven provisioning agent
│   ├── cli.py                                 # CLI entry point
│   ├── intent_parser_llm.py                   # LLM-powered intent → ClusterSpec
│   ├── llm.py                                 # Ollama REST client
│   ├── proxmox_client.py                      # Proxmox API resource discovery
│   ├── models.py                              # Data models (ClusterSpec, NodeSpec)
│   ├── config_generator.py                    # ClusterSpec → config files
│   ├── orchestrator.py                        # Pipeline runner (Packer→TF→Ansible)
│   └── README.md                              # Agent documentation
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
├── ansible/
│   ├── ansible.cfg                    # Ansible configuration
│   ├── inventory.ini                  # Node inventory (IPs and roles)
│   ├── site.yml                       # Main playbook
│   └── roles/
│       ├── common/                    # Containerd, kubeadm, kubelet, kubectl
│       ├── control_plane/             # kubeadm init, Flannel CNI
│       └── worker/                    # kubeadm join
└── README.md
```

## Prerequisites

### Software

- [Python](https://www.python.org/downloads/) >= 3.10 (for the agent)
- [Packer](https://developer.hashicorp.com/packer/downloads) >= 1.10
- [Terraform](https://www.terraform.io/downloads) >= 1.0
- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/) >= 2.12
- [xorriso](https://www.gnu.org/software/xorriso/) — `sudo apt install xorriso` (Linux)

### Proxmox

- Proxmox VE with API access
- Ubuntu 22.04 ISO uploaded to Proxmox storage (`local:iso/ubuntu-22.04.5-live-server-amd64.iso`)
- API token with VM creation privileges

---

## Quick Start

### Option A: Use the Agent (Recommended)

```bash
# Describe what you need — the agent handles everything
python -m agent create "production cluster with 5 workers and monitoring"

# Or run interactively
python -m agent create

# Preview what would be generated
python -m agent preview "ML cluster with 3 workers, 16GB RAM"
```

See [agent/README.md](agent/README.md) for full documentation.

### Option B: Manual Setup

#### 1. Build Template with Packer

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

control_plane_count = 1
worker_count        = 2
vm_name_prefix      = "k8s-node"

cp_cores      = 2
cp_memory     = 4096
worker_cores  = 2
worker_memory = 2048
```

Deploy:

```bash
terraform init
terraform plan
terraform apply
```

Example output:

```
control_plane_names = ["k8s-node-1"]
control_plane_ips   = ["10.40.19.201"]
worker_names        = ["k8s-node-2", "k8s-node-3"]
worker_ips          = ["10.40.19.202", "10.40.19.203"]
```

### 3. Set Up Kubernetes Cluster with Ansible

```bash
cd ../ansible
```

Run the playbook:

```bash
ansible-playbook site.yml
```

This will:
1. Install containerd, kubeadm, kubelet, and kubectl on all nodes
2. Initialize the control plane on `k8s-node-1` with Flannel CNI
3. Join `k8s-node-2` and `k8s-node-3` as workers
4. Print the cluster node status

Verify the cluster:

```bash
ssh ubuntu@10.40.19.201 "kubectl get nodes"
```

Expected output:

```
NAME         STATUS   ROLES           AGE   VERSION
k8s-node-1   Ready    control-plane   5m    v1.31.4
k8s-node-2   Ready    <none>          3m    v1.31.4
k8s-node-3   Ready    <none>          3m    v1.31.4
```

### 4. Tear Down

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
| `control_plane_count` | `1` | Number of control plane VMs |
| `worker_count` | `2` | Number of worker VMs |
| `vm_name_prefix` | `k8s-node` | Prefix for VM names |
| `cp_cores` | `2` | CPU cores per control plane VM |
| `cp_memory` | `4096` | Memory in MB per control plane VM |
| `worker_cores` | `2` | CPU cores per worker VM |
| `worker_memory` | `2048` | Memory in MB per worker VM |
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

Terraform passes IP configuration to each VM via a Proxmox cloud-init drive (`ide2`). Control plane nodes are provisioned first, then workers:

```
Control Plane: {vm_ip_prefix}{vm_ip_start + 0..control_plane_count-1}/24
Workers:       {vm_ip_prefix}{vm_ip_start + control_plane_count + 0..worker_count-1}/24
```

With defaults (1 CP + 2 workers): `10.40.19.201` (control plane), `10.40.19.202`, `10.40.19.203` (workers).

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
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│        3. ANSIBLE: Kubernetes Cluster            │
├──────────────────────────────────────────────────┤
│  Install containerd + kubeadm on all nodes       │
│  Initialize control plane (k8s-node-1)           │
│  Install Flannel CNI                             │
│  Join worker nodes to cluster                    │
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
| Ansible: SSH connection refused | Wait for VMs to fully boot, check IPs with `terraform output` |
| Ansible: `kubeadm init` fails | Ensure VMs have at least 2 CPUs and 1700 MB RAM |
| Ansible: workers not joining | Re-run `ansible-playbook site.yml` to regenerate join token |

---

## Important Notes

- **Credentials** — Never commit `credentials.auto.pkrvars.hcl` or `terraform.tfvars`
- **Template updates** — Rebuild with `packer build -force .`, then `terraform destroy && terraform apply`
- **Disk size** — VMs inherit the 20 GB disk from the template
- **IP range** — Default range starts at `10.40.19.201` (control plane first, then workers)

---

## Credits

Department of Computer Engineering, University of Peradeniya
