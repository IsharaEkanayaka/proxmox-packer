variable "proxmox_api_url" {
  description = "Proxmox API URL"
  type        = string
}

variable "proxmox_api_token_id" {
  description = "Proxmox API Token ID"
  type        = string
}

variable "proxmox_api_token_secret" {
  description = "Proxmox API Token Secret"
  type        = string
  sensitive   = true
}

variable "template_id" {
  description = "ID of the template to clone from"
  type        = number
  default     = 990
}

variable "target_node" {
  description = "Proxmox node to deploy VMs on"
  type        = string
  default     = "pve1"
}

variable "vm_count" {
  description = "Number of VMs to create"
  type        = number
  default     = 1
}

variable "vm_name_prefix" {
  description = "Prefix for VM names"
  type        = string
  default     = "ubuntu-vm"
}

variable "vm_cores" {
  description = "Number of CPU cores per VM"
  type        = number
  default     = 2
}

variable "vm_memory" {
  description = "Memory in MB per VM"
  type        = number
  default     = 2048
}

variable "vm_disk_size" {
  description = "Disk size (e.g., 20G)"
  type        = string
  default     = "20G"
}

variable "vm_storage" {
  description = "Storage pool for VM disks"
  type        = string
  default     = "local-lvm"
}

variable "network_bridge" {
  description = "Network bridge to use"
  type        = string
  default     = "vmbr0"
}

variable "ssh_user" {
  description = "SSH username for provisioning"
  type        = string
  default     = "ubuntu"
}

variable "ssh_password" {
  description = "SSH password for provisioning"
  type        = string
  sensitive   = true
  default     = "ubuntu"
}
