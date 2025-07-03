output "vm_ip" {
  description = "External IP of the VM"
  value       = google_compute_instance.vm.network_interface[0].access_config[0].nat_ip
}

output "kubeconfig" {
  description = "kubectl config for the cluster"
  value       = google_container_cluster.primary.endpoint 
}
