# ---------------------------------------------------------------------------
# Control Plane nodes
# ---------------------------------------------------------------------------
resource "proxmox_virtual_environment_vm" "control_plane" {
  count = var.control_plane_count

  name      = "${var.vm_name_prefix}-${count.index + 1}"
  node_name = var.target_node

  clone {
    vm_id = var.template_id
    full  = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.cp_cores
  }

  memory {
    dedicated = var.cp_memory
  }

  network_device {
    bridge = var.network_bridge
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.vm_storage
    interface    = "ide2"
    ip_config {
      ipv4 {
        address = "${var.vm_ip_prefix}${var.vm_ip_start + count.index}/24"
        gateway = var.vm_ip_gateway
      }
    }
    dns {
      servers = [var.vm_dns_server]
    }
    user_account {
      username = var.ssh_user
      password = var.ssh_password
    }
  }
}

# ---------------------------------------------------------------------------
# Worker nodes
# ---------------------------------------------------------------------------
resource "proxmox_virtual_environment_vm" "worker" {
  count = var.worker_count

  name      = "${var.vm_name_prefix}-${var.control_plane_count + count.index + 1}"
  node_name = var.target_node

  clone {
    vm_id = var.template_id
    full  = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.worker_cores
  }

  memory {
    dedicated = var.worker_memory
  }

  network_device {
    bridge = var.network_bridge
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.vm_storage
    interface    = "ide2"
    ip_config {
      ipv4 {
        address = "${var.vm_ip_prefix}${var.vm_ip_start + var.control_plane_count + count.index}/24"
        gateway = var.vm_ip_gateway
      }
    }
    dns {
      servers = [var.vm_dns_server]
    }
    user_account {
      username = var.ssh_user
      password = var.ssh_password
    }
  }

  depends_on = [proxmox_virtual_environment_vm.control_plane]
}
