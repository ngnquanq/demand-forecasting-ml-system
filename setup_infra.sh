#!/bin/bash
# to setup the infrrastructure and install related things (jenkins, docker, etc.)
# Load environment variables from .env file
if [ -f .env ]; then
  source .env
  echo "Loaded environment variables from .env"
else
  echo "Error: .env file not found! Please create a .env file with PROJECT_ID."
  exit 1
fi

# Check if GCLOUD_PROJECT_ID is set
if [ -z "$GCLOUD_PROJECT_ID" ]; then
  echo "Error: GCLOUD_PROJECT_ID not found in .env file. Please set it."
  exit 1
fi

GCP_ANSIBLE_USER="nhatquang"
INVENTORY_DIR="./inventory"
SSH_PRIVATE_KEY_FILE="~/.ssh/google_compute_engine"
VM_NAME="demandforecasting-vm" 
TERRAFORM_CONFIG_DIR="./terraform/"
REPO_DIR=$(pwd)

# login and choose the project
gcloud auth login --no-launch-browser
echo "Setting project to: $GCLOUD_PROJECT_ID"
gcloud config set project "$GCLOUD_PROJECT_ID"
echo "Project set to: $GCLOUD_PROJECT_ID"

# enable 2 main services (vm and k8s)
gcloud services enable compute.googleapis.com container.googleapis.com 

# spin up vm and k8s
cd ./infrastructure/terraform
terraform init
terraform apply -auto-approve
echo "Infrastructure provisioned successfully."

# prepare ansible w docker
cd ../jenkins
echo "Installing Docker dependencies..."
ansible-galaxy collection install community.docker
echo "Ensuring SSH key is registered with OS Login..."
# Check if the private key exists, generate if not (silently)
gcloud compute config-ssh --project "$GCLOUD_PROJECT_ID"

# Add the public key to your OS Login profile
# This only adds the key, it doesn't attempt to log in.
gcloud compute os-login ssh-keys add --key-file="$HOME/.ssh/google_compute_engine.pub"

# update ensible inventory
echo "Updating Ansible inventory..."
VM_PUBLIC_IP=$(gcloud compute instances describe demandforecasting-vm --zone "us-central1-a" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
if [ -z "$VM_PUBLIC_IP" ]; then
  echo "Error: Failed to retrieve VM public IP."
  exit 1
fi

echo "VM Public IP: $VM_PUBLIC_IP"

echo "Update the inventory file with the VM public IP..."
echo "[jenkins-vm]" > "${INVENTORY_DIR}"
# Append the VM host entry with its IP, user, and SSH key path
echo "${VM_PUBLIC_IP} ansible_user=${GCP_ANSIBLE_USER} ansible_ssh_private_key_file=${SSH_PRIVATE_KEY_FILE}" >> "${INVENTORY_DIR}"

echo "Ansible inventory updated successfully."
# run ansible playbook to install jenkins and docker
echo "ping the VM to ensure it's reachable..."
ansible -i inventory all -m ping
if [ $? -ne 0 ]; then
  echo "Error: Unable to ping the VM. Please check your network connection and VM status."
  exit 1
fi
echo "Running Ansible playbook to install Jenkins and Docker..."
ansible-playbook -i inventory jenkins.yml
echo "Jenkins and Docker installed successfully."
# Return to the infra directory
cd ../
VM_NAME="demandforecasting-vm" # Example, make sure this matches your 'google_compute_instance.vm.name'


# --- Script Logic ---

echo "--- Retrieving Jenkins Initial Admin Password ---"
echo "Project: $GCLOUD_PROJECT_ID"
echo "VM Name: $VM_NAME"
echo "-------------------------------------------------"
# Store the current directory to return later
CURRENT_DIR=$(pwd)

# navigate to the Terraform configuration directory
echo "Changing directory to Terraform config: $TERRAFORM_CONFIG_DIR"
cd "$TERRAFORM_CONFIG_DIR" || { echo "Error: Could not change to Terraform config directory."; exit 1; }

# Now, run terraform output from within the correct directory
echo "Fetching VM public IP from Terraform output..."
VM_PUBLIC_IP=$(terraform output -raw vm_ip 2>/dev/null) # Redirect stderr to null for clean output

# Return to the original directory before proceeding
cd "$CURRENT_DIR" || { echo "Error: Could not return to original directory."; exit 1; }


if [ -z "$VM_PUBLIC_IP" ]; then
  echo "Error: Could not retrieve VM public IP. Ensure 'terraform apply' completed successfully and 'vm_ip' output is defined."
  exit 1
fi
echo "VM Public IP: $VM_PUBLIC_IP"

echo "Fetching VM zone..."
VM_ZONE=$(gcloud compute instances describe "$VM_NAME" \
  --project="$GCLOUD_PROJECT_ID" \
  --format='value(zone)' | rev | cut -d'/' -f1 | rev 2>/dev/null)

if [ -z "$VM_ZONE" ]; then
  echo "Error: Could not determine the zone for VM '$VM_NAME'."
  echo "Please check if the VM exists and your project ID is correct."
  exit 1
fi
echo "VM Zone: $VM_ZONE"

REMOTE_COMMAND="
  JENKINS_CONTAINER_ID=\$(sudo docker ps -q -f name=jenkins)
  if [ -z \"\$JENKINS_CONTAINER_ID\" ]; then
    echo 'REMOTE_ERROR: Jenkins Docker container not found or not running. Is Jenkins fully started?' >&2
    exit 1
  fi
  sudo docker exec \$JENKINS_CONTAINER_ID cat /var/jenkins_home/secrets/initialAdminPassword
"

echo "Waiting for Jenkins to fully initialize (approx. 60-120 seconds)..."
#sleep 120 

#execute the remote command using gcloud compute ssh
echo "Attempting to retrieve password from VM..."
SSH_OUTPUT=$(gcloud compute ssh "$VM_NAME" \
  --zone="$VM_ZONE" \
  --project="$GCLOUD_PROJECT_ID" \
  --quiet \
  --command="$REMOTE_COMMAND" 2>&1) 

if [ $? -ne 0 ]; then
  echo "Error: SSH command to '$VM_NAME' failed. Check connectivity, VM status, and gcloud authentication."
  echo "SSH output (for debugging):"
  echo "$SSH_OUTPUT"
  exit 1
fi

JENKINS_INITIAL_ADMIN_PASSWORD=$(echo "$SSH_OUTPUT" | grep -v "REMOTE_ERROR" | tail -n 1)

if [[ "$SSH_OUTPUT" == *"REMOTE_ERROR"* || -z "$JENKINS_INITIAL_ADMIN_PASSWORD" ]]; then
    echo "Error: Jenkins password could not be retrieved. Possible issues:"
    echo "- Jenkins Docker container not running or not named 'jenkins'."
    echo "- Jenkins not fully started yet on the VM."
    echo "- Permissions issues on the VM."
    echo "Full remote command output for debugging:"
    echo "$SSH_OUTPUT"
    echo "---"
    echo "Manual Retrieval Hint:"
    echo "  You can try manually with: gcloud compute ssh --zone \"$VM_ZONE\" \"$VM_NAME\" --project \"$GCLOUD_PROJECT_ID\" --command=\"docker exec \$(docker ps -q -f name=jenkins) cat /var/lib/jenkins/secrets/initialAdminPassword\""
    exit 1
fi

echo ""
echo "--------------------------------------------------------"
echo "  Jenkins Initial Admin Password:"
echo "  $JENKINS_INITIAL_ADMIN_PASSWORD"
echo "--------------------------------------------------------"
echo ""
echo "You can access Jenkins at http://$VM_PUBLIC_IP:8080/ (or your configured port)."
echo "Use the password above to complete the setup."
echo "--------------------------------------------------------"

echo "Setup completed successfully. You can now access Jenkins at http://$VM_PUBLIC_IP:8080"

echo "--------------------------------------------------------"
# Setup Kubernetes cluster
echo "Setup k8s cluster..."
echo "Connect to the Kubernetes cluster using gcloud cli"
gcloud container clusters get-credentials application-gke --zone "$VM_ZONE" --project "$GCLOUD_PROJECT_ID"
echo "Kubernetes cluster connected successfully."
echo "--------------------------------------------------------"
# Create binding for the Jenkins service
echo "Creating Kubernetes service account and binding for Jenkins..."
cd $REPO_DIR
kubectl create ns model-serving
kubectl create ns ingress
kubectl create ns logging
kubectl create ns monitoring
kubectl create ns tracing

# kubectl apply -f ./helm-charts/jenkins-namespace-creator-rbac.yaml
kubectl create clusterrolebinding model-serving-admin-binding \
  --clusterrole=admin \
  --serviceaccount=model-serving:default \
  --namespace=model-serving

kubectl create clusterrolebinding anonymous-admin-binding \
  --clusterrole=admin \
  --user=system:anonymous \
  --namespace=model-serving

kubectl create clusterrolebinding jenkins-elk-deployer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=model-serving:default
echo "Kubernetes service account and binding created successfully."
echo "--------------------------------------------------------"
echo "Setup load balancer for application..."
# Create a load balancer for the application
helm upgrade --install traefik ./helm-charts/traefik \
  --namespace ingress \
  -f ./helm-charts/traefik/values.yaml 

echo "Waiting for Traefik deployment to be ready (up to 5 minutes)..."
kubectl rollout status deployment/traefik -n ingress --timeout=5m
if [ $? -ne 0 ]; then
    echo "Error: Traefik deployment didn't become ready in time. Exiting."
    exit 1
fi

echo "Load balancer for application created successfully."
echo "Promote external IP to static..."
EXTERNAL_IP=$(kubectl get svc -n ingress traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
gcloud compute addresses create traefik-static-ip \
  --addresses "$EXTERNAL_IP" \
  --region "$GCP_REGION"

echo "Attempted to promote IP '$EXTERNAL_IP' to static IP 'traefik-static-ip'."
yq e ".ingress.host = \"$EXTERNAL_IP\"" -i ./helm-charts/application/values.yaml
yq e ".service.spec.loadBalancerIP = \"$EXTERNAL_IP\"" -i ./helm-charts/traefik/values.yaml
echo "Updated application values.yaml with static IP: $EXTERNAL_IP"
echo "Setup completed successfully. You can now access your application at http://$EXTERNAL_IP"
echo "--------------------------------------------------------"
echo "Setup tracing for the application..."
# Setup tracing for the application
helm upgrade --install jaeger ./helm-charts/jaeger \
  --namespace tracing \
  -f ./helm-charts/jaeger/values.yaml
if [ $? -ne 0 ]; then
    echo "Error: Jaeger Helm installation/upgrade failed. Exiting."
    exit 1
fi
echo "Jaeger Helm chart command finished."

# Wait for Jaeger's deployment to be fully ready. Stop if it takes too long.
echo "Waiting for Jaeger deployment to be ready (up to 5-10 minutes)..."
kubectl rollout status deployment/jaeger-query -n tracing --timeout=10m

# Check if Jaeger pods are ready. If not, stop.
if [ $? -ne 0 ]; then
    echo "Error: Jaeger deployment didn't become ready in time. Exiting."
    exit 1
fi
echo "Tracing setup completed successfully."
echo "--------------------------------------------------------"
echo "Setup logging for the application..."
# Setup logging for the application
helm upgrade --install elasticsearch ./helm-charts/elk/elasticsearch \
  --namespace logging \
  -f ./helm-charts/elk/elasticsearch/values.yaml
kubectl rollout status statefulset/elasticsearch-master -n logging --timeout=10m
if [ $? -ne 0 ]; then echo "Error: Elasticsearch didn't become ready. Exiting."; exit 1; fi
echo "Elasticsearch is ready."


helm upgrade --install logstash ./helm-charts/elk/logstash \
  --namespace logging \
  -f ./helm-charts/elk/logstash/logstash-values.yaml
kubectl rollout status statefulset/logstash-logstash -n logging --timeout=5m
if [ $? -ne 0 ]; then echo "Error: Logstash didn't become ready. Exiting."; exit 1; fi
echo "Logstash is ready."

helm upgrade --install filebeat ./helm-charts/elk/filebeat \
  --namespace logging \
  -f ./helm-charts/elk/filebeat/filebeat-values.yaml
kubectl rollout status daemonset/filebeat-filebeat -n logging --timeout=5m
if [ $? -ne 0 ]; then echo "Error: Filebeat didn't become ready. Exiting."; exit 1; fi
echo "Filebeat is ready."

helm upgrade --install kibana ./helm-charts/elk/kibana \
  --namespace logging \
  -f ./helm-charts/elk/kibana/kibana-values.yaml
kubectl rollout status deployment/kibana-kibana -n logging --timeout=5m
if [ $? -ne 0 ]; then echo "Error: Kibana didn't become ready. Exiting."; exit 1; fi
echo "Kibana is ready."


echo "Logging setup approximately 2 minutes..."
sleep 120
echo "Logging setup completed successfully."
echo "To get Kibana username and password, run the following command:"
echo "kubectl get secret elasticsearch-master-credentials -n logging -o jsonpath='{.data.username}' | base64 --decode"
echo "kubectl get secret elasticsearch-master-credentials -n logging -o jsonpath='{.data.password}' | base64 --decode"
echo "--------------------------------------------------------"
echo "Setup monitoring for the application..."
# Setup monitoring for the application
helm upgrade --install monitoring ./helm-charts/kube-prometheus-stack \
  --namespace monitoring \
  -f ./helm-charts/kube-prometheus-stack/values.yaml
echo "Monitoring setup approximately 2 minutes..."
sleep 120
echo "Monitoring setup completed successfully."
echo "You can access the Prometheus dashboard using port fowarding"
echo "Username: admin"
echo "Password: prom-operator"
echo "Monitoring setup completed successfully."
echo "--------------------------------------------------------"