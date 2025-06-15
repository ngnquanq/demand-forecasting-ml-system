pipeline {

    agent any
    
    environment {
        application_registry            = 'ngnquanq/demand-forecasting'
        application_tag                  = 'latest'
        jenkins_registry                = 'ngnquanq/custom-jenkins'
        dockerhub_registryCredentialID  = 'dockerhub'
        HELM_RELEASE_NAME                = 'application' // This is the Helm release name
        HELM_CHART_PATH                  = './helm-charts/application' // Assuming this is the correct path to your chart
        KUBE_CREDENTIAL_ID               = 'gke-kubeconfig'
        KUBE_NAMESPACE                   = 'model-serving'
        KUBE_DEPLOYMENT_NAME             = 'application' // Assuming your Kubernetes Deployment is also named 'application' (common for Helm)
        
        // Logging related
        KUBE_LOGGING_NAMESPACE           = 'logging'
        HELM_ES_RELEASE_NAME             = 'elasticsearch'
        HELM_ES_CHART_PATH               = 'elastic/elasticsearch' // This is the chart repo path
        HELM_FILEBEAT_RELEASE_NAME       = 'filebeat'
        HELM_FILEBEAT_CHART_PATH         = 'elastic/filebeat'
        HELM_LOGSTASH_RELEASE_NAME       = 'logstash'
        HELM_LOGSTASH_CHART_PATH         = 'elastic/logstash'
        HELM_KIBANA_RELEASE_NAME         = 'kibana'
        HELM_KIBANA_CHART_PATH           = 'elastic/kibana'
        ELK_VALUES_PATH                  = './helm-charts/elk' // Common path for ELK values files

        // Monitoring related
        KUBE_MONITORING_NAMESPACE        = 'monitoring' // Common practice to use 'monitoring' namespace
        HELM_MONITORING_RELEASE_NAME     = 'monitoring'
        HELM_PROMETHEUS_CHART_REPO       = 'prometheus-community'
        HELM_PROMETHEUS_CHART_NAME       = 'kube-prometheus-stack'
        HELM_PROMETHEUS_CHART_VERSION    = '45.7.1'
        // Assuming the extracted chart path will be './kube-prometheus-stack/'
        HELM_PROMETHEUS_LOCAL_CHART_PATH = './helm-charts/kube-prometheus-stack'    
        GRAFANA_LOCAL_PORT            = '8081'
        PROMETHEUS_LOCAL_PORT       = '8082'
    }

    stages {
        //1. Testing
        stage('Setup') {
            steps {
                script {
                    echo 'Setting up environment...'
                    withPythonEnv('python3'){
                        sh 'python -m pip install --upgrade pip'
                        sh 'python -m pip install -r requirements.txt'
                        //sh 'python -m pip install -r requirements-dev.txt'
                    }
                    echo 'Environment setup complete!'
                }
            }
        }
        stage('Test') {
            steps {
            script {
                echo '🔍 Running tests with coverage guard…'
                withPythonEnv('python3') {
                // Run pytest including coverage threshold; capture exit code
                def status = sh(
                    script: 'python -m pytest --cov=src --cov-fail-under=80 src/test',
                    returnStatus: true
                )
                if (status != 0) {
                    // Either tests failed or coverage < 80%
                    error "❌ Tests failed or coverage below 80% (exit code: ${status})"
                }
                echo '✅ All tests passed and coverage ≥ 80%'
                }
            }
            }
        }
        // 2. Build and Push
        stage('Build') {
            steps {
                script {
                    // echo 'Freezing docker related things for now '
                    echo 'Building Docker image model image...'
                    sh 'docker build -t $application_registry .'
                    echo 'Building Docker image jenkins image...'
                    sh 'docker build -t $jenkins_registry ./infrastructure/config/'
                }
            }
        }
        stage('Push') {
            steps {
                script {
                    
                    withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                                     usernameVariable: 'DOCKER_USER',
                                                     passwordVariable: 'DOCKER_PASS')]) {
                        sh 'docker login -u $DOCKER_USER -p $DOCKER_PASS'
                        echo 'Docker login successful!'
                        // echo 'Freezing docker related things for now '
                        sh 'docker tag $application_registry $application_registry:$application_tag'
                        sh 'docker tag $jenkins_registry $jenkins_registry:$application_tag'
                        sh 'docker push $application_registry:$application_tag'
                        sh 'docker push $jenkins_registry:$application_tag'
                        echo 'Pushing Docker image to Docker Hub...'
                        echo 'Pushing Docker image to Docker Hub jenkins image...'
                        echo 'Docker image pushed successfully!'
                        echo 'Docker image pushed successfully jenkins image!'
                    }
                }
            }
        }
        // 3. Deploy
        stage('Deploy the main application') {
            agent {
                kubernetes {
                    containerTemplate{
                        name 'helm'
                        image 'ngnquanq/custom-jenkins:latest'
                        alwaysPullImage true
                    }
                }
            }
            steps {
                script {
                    container('helm') {
                        // 1. Deploy/Upgrade the application with Helm
                        echo "Deploying/Upgrading Helm release '${env.HELM_RELEASE_NAME}' in namespace '${env.KUBE_NAMESPACE}'..."
                        sh("helm upgrade --install ${env.HELM_RELEASE_NAME} ${env.HELM_CHART_PATH} --namespace ${env.KUBE_NAMESPACE}")
                        echo "Helm deployment/upgrade complete."

                        // 2. Trigger a rollout restart to ensure new image pull
                        echo "Triggering rollout restart for deployment '${env.KUBE_DEPLOYMENT_NAME}' in namespace '${env.KUBE_NAMESPACE}'..."
                        sh("kubectl rollout restart deployment/${env.KUBE_DEPLOYMENT_NAME} -n ${env.KUBE_NAMESPACE}")
                        echo "Rollout restart triggered."

                        // 3. Wait for rollout to complete (optional but recommended for stability)
                        echo "Waiting for deployment '${env.KUBE_DEPLOYMENT_NAME}' rollout to complete..."
                        sh("kubectl rollout status deployment/${env.KUBE_DEPLOYMENT_NAME} -n ${env.KUBE_NAMESPACE} --timeout=5m") // Adjust timeout as needed
                        echo "Deployment rollout complete."

                        // 2. Wait for External IP and check Swagger
                        def serviceName = "application" // Assuming your service is named 'application'
                        def namespace = "model-serving"
                        def externalIp = ""
                        def maxAttempts = 20 // Adjust as needed, e.g., 20 attempts * 15 seconds = 5 minutes
                        def attempt = 0
                        def swaggerUp = false

                        echo "Waiting for external IP for service '${serviceName}' in namespace '${namespace}'..."

                        while (externalIp == "" && attempt < maxAttempts) {
                            attempt++
                            try {
                                externalIp = sh(script: "kubectl get svc ${serviceName} -n ${namespace} -o jsonpath='{.status.loadBalancer.ingress[0].ip}'", returnStdout: true).trim()
                            } catch (Exception e) {
                                echo "Attempt ${attempt}: Service not found or IP not yet assigned. Retrying in 15 seconds..."
                                // This might happen if the service is still being provisioned
                            }

                            if (externalIp == "") {
                                sleep(time: 15, unit: 'SECONDS') // Wait for 15 seconds before retrying
                            }
                        }

                        if (externalIp == "") {
                            error("Failed to get external IP for service '${serviceName}' after ${maxAttempts} attempts.")
                        } else {
                            echo "External IP found: ${externalIp}"

                            echo "Checking if Swagger is up at http://${externalIp}:8000/docs..."
                            def swaggerAttempts = 10 // Max attempts to check swagger
                            def swaggerAttempt = 0

                            while (!swaggerUp && swaggerAttempt < swaggerAttempts) {
                                swaggerAttempt++
                                try {
                                    def httpCode = sh(script: "curl -s -o /dev/null -w \"%{http_code}\" http://${externalIp}:8000/docs", returnStdout: true).trim()
                                    if (httpCode == "200") {
                                        swaggerUp = true
                                        echo "Swagger is up! (HTTP 200)"
                                    } else {
                                        echo "Attempt ${swaggerAttempt}: Swagger not yet up (HTTP ${httpCode}). Retrying in 10 seconds..."
                                        sleep(time: 10, unit: 'SECONDS')
                                    }
                                } catch (Exception e) {
                                    echo "Attempt ${swaggerAttempt}: Error checking Swagger: ${e.getMessage()}. Retrying in 10 seconds..."
                                    sleep(time: 10, unit: 'SECONDS')
                                }
                            }

                            if (!swaggerUp) {
                                error("Swagger did not come up after ${swaggerAttempts} attempts.")
                            }
                        }
                    }
                }
            }
        }
        // 4. Deploy ELK Stack
        stage('Deploy Observability Stack (ELK & Monitoring)') {
            agent {
                kubernetes {
                    containerTemplate{
                        name 'helm'
                        image 'ngnquanq/custom-jenkins:latest'
                        alwaysPullImage true
                    }
                }
            }
            steps {
                script {
                    container('helm') {
                        // --- ELK STACK DEPLOYMENT ---
                        echo "--- Deploying ELK Stack ---"

                        echo "Adding Elastic Helm repo..."
                        sh "helm repo add elastic https://helm.elastic.co"
                        sh "helm repo update" // Update after adding repo

                        echo "Deploying Elasticsearch..."
                        sh "helm upgrade --install ${env.HELM_ES_RELEASE_NAME} ${env.HELM_ES_CHART_PATH} -f ${env.ELK_VALUES_PATH}/elasticsearch-values.yaml --namespace ${env.KUBE_LOGGING_NAMESPACE}"

                        echo "Waiting for Elasticsearch StatefulSet to be ready..."
                        sh "kubectl rollout status statefulset/${env.HELM_ES_RELEASE_NAME}-master -n ${env.KUBE_LOGGING_NAMESPACE} --timeout=10m"
                        echo "Elasticsearch StatefulSet is ready."

                        // Corrected order: Logstash before Filebeat
                        echo "Deploying Logstash..."
                        sh "helm upgrade --install ${env.HELM_LOGSTASH_RELEASE_NAME} ${env.HELM_LOGSTASH_CHART_PATH} -f ${env.ELK_VALUES_PATH}/logstash-values.yaml --namespace ${env.KUBE_LOGGING_NAMESPACE}"

                        echo "Waiting for Logstash StatefulSet to be ready..."
                        sh "kubectl rollout status statefulset/${env.HELM_LOGSTASH_RELEASE_NAME}-logstash -n ${env.KUBE_LOGGING_NAMESPACE} --timeout=5m"
                        echo "Logstash StatefulSet is ready."

                        echo "Deploying Filebeat..."
                        sh "helm upgrade --install ${env.HELM_FILEBEAT_RELEASE_NAME} ${env.HELM_FILEBEAT_CHART_PATH} -f ${env.ELK_VALUES_PATH}/filebeat-values.yaml --namespace ${env.KUBE_LOGGING_NAMESPACE}"

                        echo "Waiting for Filebeat DaemonSet to be ready..."
                        sh "kubectl rollout status daemonset/${env.HELM_FILEBEAT_RELEASE_NAME}-filebeat -n ${env.KUBE_LOGGING_NAMESPACE} --timeout=10m"
                        echo "Filebeat DaemonSet is ready."

                        echo "Deploying Kibana..."
                        // sh "helm upgrade --install ${env.HELM_KIBANA_RELEASE_NAME} ${env.HELM_KIBANA_CHART_PATH} -f ${env.ELK_VALUES_PATH}/kibana-values.yaml --namespace ${env.KUBE_LOGGING_NAMESPACE}"

                        echo "ELK Stack deployment initiated. Waiting for Kibana to become ready..."
                        echo "Waiting for Kibana pod to be running..."
                        // sh "kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kibana,app.kubernetes.io/instance=${env.HELM_KIBANA_RELEASE_NAME} -n ${env.KUBE_LOGGING_NAMESPACE} --timeout=5m"

                        // Retrieve Elasticsearch credentials for Kibana login
                        echo "Retrieving Kibana login credentials..."
                        def esUsername = sh(script: "kubectl get secret ${env.HELM_ES_RELEASE_NAME}-master-credentials -n ${env.KUBE_LOGGING_NAMESPACE} -o jsonpath='{.data.username}' | base64 --decode", returnStdout: true).trim()
                        def esPassword = sh(script: "kubectl get secret ${env.HELM_ES_RELEASE_NAME}-master-credentials -n ${env.KUBE_LOGGING_NAMESPACE} -o jsonpath='{.data.password}' | base64 --decode", returnStdout: true).trim()

                        echo """
                            ===================================================================
                                            Kibana Access Information
                            ===================================================================
                            Kibana is likely available via port-forwarding.
                            Run the following command in your local terminal to access Kibana:

                            kubectl port-forward --namespace ${env.KUBE_LOGGING_NAMESPACE} \\
                                \$(kubectl get pod --namespace ${env.KUBE_LOGGING_NAMESPACE} --selector="app.kubernetes.io/name=kibana,app.kubernetes.io/instance=${env.HELM_KIBANA_RELEASE_NAME}" \\
                                --output jsonpath='{.items[0].metadata.name}') 8080:5601

                            Then, navigate to: http://localhost:8080

                            Login with these credentials:
                            Username: ${esUsername}
                            Password: ${esPassword}
                            ===================================================================
                            """

                        // --- MONITORING STACK DEPLOYMENT ---
                        echo "--- Deploying Monitoring Stack (Prometheus & Grafana) ---"

                        echo "Adding Prometheus Community Helm repo..."
                        sh "helm repo add ${env.HELM_PROMETHEUS_CHART_REPO} https://prometheus-community.github.io/helm-charts"
                        sh "helm repo update" // Update after adding repo

                        echo "Deploying Prometheus/Grafana (kube-prometheus-stack)..."
                        sh "helm upgrade --install ${env.HELM_MONITORING_RELEASE_NAME} ${env.HELM_PROMETHEUS_LOCAL_CHART_PATH} --namespace ${env.KUBE_MONITORING_NAMESPACE}"

                        echo "Monitoring Stack deployment initiated. Waiting for Grafana to become ready..."
                        echo "Waiting for Grafana pod to be running..."
                        sh "kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana,app.kubernetes.io/instance=${env.HELM_MONITORING_RELEASE_NAME} -n ${env.KUBE_MONITORING_NAMESPACE} --timeout=5m"
                        echo """
                        ===================================================================
                                    Grafana & Prometheus Access Information
                        ===================================================================
                        Grafana (default admin:prom-operator) is likely available via port-forwarding.
                        Run the following command in your local terminal to access Grafana:

                        kubectl port-forward --namespace ${env.KUBE_MONITORING_NAMESPACE} \\
                            svc/${env.HELM_MONITORING_RELEASE_NAME}-grafana ${env.GRAFANA_LOCAL_PORT}:80

                        Then, navigate to: http://localhost:${env.GRAFANA_LOCAL_PORT}
                        Login with default credentials (admin/prom-operator) or your custom ones if configured.
                        Remember to change the default Grafana password!

                        Prometheus UI (no authentication) is likely available via port-forwarding.
                        Run the following command in your local terminal to access Prometheus:

                        kubectl port-forward --namespace ${env.KUBE_MONITORING_NAMESPACE} \\
                            svc/${env.HELM_MONITORING_RELEASE_NAME}-kube-prometheus-prometheus ${env.PROMETHEUS_LOCAL_PORT}:9090

                        Then, navigate to: http://localhost:${env.PROMETHEUS_LOCAL_PORT}
                        ===================================================================
                        """
                    }
                }
            }
        }

    }
    post {
        success {
            script {
                withCredentials([string(credentialsId: 'discord', variable: 'DISCORD_WEBHOOK_URL')]) {
                    discordSend description: "Build succeeded!",
                                webhookURL: "${DISCORD_WEBHOOK_URL}",
                                title: "Deployment Successful & Observability Details"
                                // color: "00FF00" // Green color for success
                }
            }
        }
        failure {
            script {
                withCredentials([string(credentialsId: 'discord', variable: 'DISCORD_WEBHOOK_URL')]) {
                    discordSend description: 'Build failed! Check Jenkins for details.',
                                webhookURL: "${DISCORD_WEBHOOK_URL}",
                                title: "Deployment Failed"
                                // color: "FF0000" // Red color for failure
                }
            }
        }
    }
}
