variable "proxmox_api_url" {
  type    = string
  default = ""
}

variable "proxmox_api_token_id" {
  type    = string
  default = ""
}

variable "proxmox_api_token_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "ssh_bastion_username" {
	type    = string
	default = ""
}

variable "ssh_bastion_password" {
  type      = string
  default   = ""
  sensitive = true
}

packer {
  required_plugins {
    proxmox = {
      version = ">= 1.1.3"
      source  = "github.com/hashicorp/proxmox"
    }
  }
}

source "proxmox-iso" "ubuntu-server" {
  # --- Connection & Hardware ---
  proxmox_url = var.proxmox_api_url
  username    = var.proxmox_api_token_id
  token       = var.proxmox_api_token_secret
  insecure_skip_tls_verify = true
  
  node      = "pve1"
  vm_id     = "990"
  vm_name   = "ubuntu-server-template"
  
  boot_iso {
    type = "ide"   # Explicitly set the bus type
    iso_file = "local:iso/ubuntu-22.04.5-live-server-amd64.iso"
    unmount = true
  }
  qemu_agent       = true
  cores            = 2
  memory           = 2048
  scsi_controller  = "virtio-scsi-pci"

  disks {
    disk_size    = "20G"
    format       = "raw"
    storage_pool = "local-lvm"
    type         = "scsi"
  }

  network_adapters {
    model    = "virtio"
    bridge   = "vmbr0"
    firewall = "false"
  }

  # --- Cloud-Init CD Configuration ---
  # This creates a small ISO with your config files and uploads it to Proxmox
  additional_iso_files {
    cd_files = ["./http/user-data", "./http/meta-data"]
    cd_label = "cidata"
    iso_storage_pool = "local"
    type     = "ide"     
    index    = 3           # <--- Force it to the secondary slot (ide3)
  }

  # --- UPDATED: Boot Command ---
  boot_wait = "10s"
  
  boot_command = [
    "c",
    "<wait2>",
    # logic: ds=nocloud;s=/cdrom/ tells Ubuntu to look at the attached CD drive
    "linux /casper/vmlinuz --- autoinstall ds=nocloud;s=/cdrom/",
    "<enter>",
    "<wait2>",
    "initrd /casper/initrd",
    "<enter>",
    "<wait2>",
    "boot<enter>"
  ]

  ssh_username = "ubuntu"
  ssh_password = "ubuntu"
  ssh_timeout  = "30m"
  ssh_handshake_attempts = 100

  # --- Bastion Host Settings ---
  # This tells Packer: "To reach the VM, go through Tesla first"
  ssh_bastion_host     = "tesla.ce.pdn.ac.lk"
  ssh_bastion_username = var.ssh_bastion_username
  # If you use a password for Tesla:
  ssh_bastion_password = var.ssh_bastion_password
  # If you use an SSH key/agent for Tesla, Packer will use it automatically.
}

build {
  sources = ["source.proxmox-iso.ubuntu-server"]
}