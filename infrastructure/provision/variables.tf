variable "project_id" {}
variable "region"  { default = "us-central1" }
variable "zone"    { default = "us-central1-a" }

variable "vm_name"      { default = "demandforecasting-vm" }
variable "machine_type" { default = "e2-medium" }  # free-tier eligible
variable "gke_name"     { default = "application-gke" }
