resource "google_compute_instance" "vm" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 15
    }
  }

  network_interface {
    network = "default"
    access_config {}

  }

  // Assign http tag to allow http traffic
  tags = ["http-server","web-server", "my-app-vm"]

  metadata_startup_script = <<-EOS
    #!/bin/bash
    sudo apt-get update -y && sudo apt-get install -y nginx
  EOS
}

resource "google_compute_firewall" "allow_web_and_custom_ports" {
  name    = "${var.vm_name}-allow-web-and-custom"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8080", "50000", "8000"]
  }

  source_ranges = ["0.0.0.0/0"] # Allows traffic from any IP
  
  // Apply this firewall rule only to instances with the "web-server" tag
  target_tags = ["web-server"]
}

resource "google_container_cluster" "primary" {
  name     = "application-gke"
  location = var.zone

  // Enabling Autopilot for this cluster
  enable_autopilot = false

  //Delete protetion false
  deletion_protection = false

  // Specify the initial number of nodes
  initial_node_count = 2

  // Node configuration
  node_config {
    machine_type = "e2-standard-4" // 4 vCPUs, 16 GB RAM
    disk_size_gb = 25
  }
}
