resource "proxmox_virtual_environment_vm" "ubuntu_vm" {
  count = var.vm_count

  name        = "${var.vm_name_prefix}-${count.index + 1}"
  node_name   = var.target_node
  
  clone {
    vm_id = var.template_id
    full  = true
  }

  agent {
    enabled = true
  }

  cpu {
    cores = var.vm_cores
  }

  memory {
    dedicated = var.vm_memory
  }

  network_device {
    bridge = var.network_bridge
  }

  operating_system {
    type = "l26"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }
    user_account {
      username = var.ssh_user
      password = var.ssh_password
    }
  }
}
