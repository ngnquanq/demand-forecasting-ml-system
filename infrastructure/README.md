# Head First !

This directory contains Terraform, Ansible scripts to run and set up the demonstration environment

## Overview
- **provision** – Terraform configuration for creating the VM, firewall rules and optional GKE cluster.
- **config** – Ansible inventory, playbooks and supporting files for configuring Jenkins and Kubernetes.


## Authenticate to Google Cloud
Authenticate Terraform via Application Default Credentials
```shell
# Authenticate terraform via ADC
gcloud auth application-default login             
gcloud config set project <YOUR_PROJECT_ID>
```
Enable all related APIs
```shell
# Enables Required APIs (Make sure that you have linked w ur billing account)
gcloud services enable compute.googleapis.com container.googleapis.com # We only use these 2 at the moment
```

## Configure Terraform
Edit `provision/variables.tf` to match your environment. The most important variable is `project_id` which should contain your GCP project identifier. Other variables such as `region`, `zone`, `vm_name` and `gke_name` can also be overridden.

Initialize and apply the configuration:
```shell
cd provision
terraform init
terraform apply
cd ../config
```

## Prepare Ansible
Install the Docker collection and create an SSH key that will be used to connect to the VM:

```shell
ansible-galaxy collection install community.docker
```

Remember to create a SSH key as well
```shell
gcloud compute ssh --zone "us-central1-a" "demandforecasting-vm" --project "global-phalanx-449403-d2"
gcloud compute ssh --zone <YOUR_VM_ZONE> <YOUR_VM_NAME> --project <YOUR_PROJECT_ID>
gcloud compute os-login ssh-keys add \
    --key-file=/home/<YOUR_USER_NAME/.ssh/google_compute_engine.pub
```

Edit `config/inventory` and replace the placeholder values with your VM IP address and username:
```shell
[jenkins-vm]
<VM_PUBLIC_IP> ansible_user=<GCP_USERNAME> ansible_ssh_private_key_file=~/.ssh/google_compute_engine
```

Check connectivity and run the Jenkins playbook:
```shell
ansible -i inventory all -m ping
ansible-playbook -i inventory jenkins.yml
```

7. Then, access the VM and open Jenkins (remmember to allow Http Traffic on this VM as well)

8. After that, install all required plugins, including:
- Kubernetes
- Discord notifier

## Accessing the Kubernetes Cluster
gke-gcloud-auth-plugin is required for running remote GKE. Install the authentication plugin and retrieve cluster credentials:

```shell
# Install the plugin
sudo apt-get install google-cloud-cli-gke-gcloud-auth-plugin
# Now check it's version
gke-gcloud-auth-plugin --version
```

After that, we need to connect with GKE cluster via CLI
```shell
# Now we can connect via cli
gcloud container clusters get-credentials demandforecasting-gke --region us-central1 --project global-phalanx-449403-d2
```