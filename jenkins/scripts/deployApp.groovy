// jenkins/scripts/deployApp.groovy
def call(env, applicationImageWithTag) { 
    def namespace = "model-serving"
    def ingressNamespace = "ingress" 
    def ingressServiceName = "traefik"
    def deploymentName = env.KUBE_DEPLOYMENT_NAME
    def releaseName = env.HELM_RELEASE_NAME
    def chartPath = env.HELM_CHART_PATH

    // Parse the full image tag into repository and tag
    def applicationImageParts = applicationImageWithTag.split(':')
    def repository = applicationImageParts[0]
    def tag = applicationImageParts[1]

    // 1. Deploy/Upgrade with Helm
    echo "Deploying/upgrading Helm release '${releaseName}' in namespace '${namespace}' with image: ${repository}:${tag}..."
    // Crucial Change: Add --set flags to override image.repository and image.tag in values.yaml
    sh """
        helm upgrade --install ${releaseName} ${chartPath} \\
            --namespace ${namespace} \\
            --set image.repository=${repository} \\
            --set image.tag=${tag} \\
            --wait 
    """
    echo "Helm deployment/upgrade complete."

    // 2. Rollout restart
    echo "Initiating rollout restart for deployment/${deploymentName}..."
    sh "kubectl rollout restart deployment/${deploymentName} -n ${namespace}"
    sh "kubectl rollout status deployment/${deploymentName} -n ${namespace} --timeout=5m"
    echo "Rollout completed."

    // 3. Wait for external IP (assuming this is the Traefik LoadBalancer IP)
    def externalIp = ""
    def maxAttempts = 20
    def attempt = 0
    echo "Waiting for external IP of ${ingressServiceName} in ${ingressNamespace} namespace..."
    while (externalIp == "" && attempt < maxAttempts) {
        attempt++
        try {
            externalIp = sh(script: "kubectl get svc ${ingressServiceName} -n ${ingressNamespace} -o jsonpath='{.status.loadBalancer.ingress[0].ip}'", returnStdout: true).trim()
        } catch (e) {
            echo "Attempt ${attempt}: Still waiting for external IP (error: ${e.getMessage()})"
        }
        if (externalIp == "") {
            sleep 15 
        }
    }

    if (externalIp == "") {
        error "Failed to get external IP for ${ingressServiceName} after ${maxAttempts} attempts."
    }

    echo "External IP: ${externalIp}"

    // 4. Check Swagger
    def swaggerUp = false
    def swaggerAttempts = 10
    def swaggerAttempt = 0
    echo "Checking Swagger UI at http://${externalIp}/docs..."

    while (!swaggerUp && swaggerAttempt < swaggerAttempts) {
        swaggerAttempt++
        try {
            def httpCode = sh(script: "curl -s -o /dev/null -w \"%{http_code}\" http://${externalIp}/docs", returnStdout: true).trim()
            if (httpCode == "200") {
                swaggerUp = true
                echo "Swagger is UP! (HTTP ${httpCode})"
            } else {
                echo "Attempt ${swaggerAttempt}: Swagger not ready (HTTP ${httpCode})"
            }
        } catch (e) {
            echo "Attempt ${swaggerAttempt}: Error checking Swagger: ${e.getMessage()}"
        }
        if (!swaggerUp) {
            sleep 10
        }
    }

    if (!swaggerUp) {
        error "Swagger never became ready after ${swaggerAttempts} attempts."
    }
}

return this