output "vm_ids" {
  description = "IDs of created VMs"
  value       = proxmox_virtual_environment_vm.ubuntu_vm[*].vm_id
}

output "vm_names" {
  description = "Names of created VMs"
  value       = proxmox_virtual_environment_vm.ubuntu_vm[*].name
}

output "vm_ip_addresses" {
  description = "Primary IP addresses of created VMs"
  value = [
    for vm in proxmox_virtual_environment_vm.ubuntu_vm :
    try(vm.ipv4_addresses[1][0], "pending")
  ]
}
