output "control_plane_ids" {
  description = "IDs of control plane VMs"
  value       = proxmox_virtual_environment_vm.control_plane[*].vm_id
}

output "worker_ids" {
  description = "IDs of worker VMs"
  value       = proxmox_virtual_environment_vm.worker[*].vm_id
}

output "control_plane_names" {
  description = "Names of control plane VMs"
  value       = proxmox_virtual_environment_vm.control_plane[*].name
}

output "worker_names" {
  description = "Names of worker VMs"
  value       = proxmox_virtual_environment_vm.worker[*].name
}

output "control_plane_ips" {
  description = "IP addresses of control plane VMs"
  value = [
    for vm in proxmox_virtual_environment_vm.control_plane :
    try(vm.ipv4_addresses[1][0], "pending")
  ]
}

output "worker_ips" {
  description = "IP addresses of worker VMs"
  value = [
    for vm in proxmox_virtual_environment_vm.worker :
    try(vm.ipv4_addresses[1][0], "pending")
  ]
}
