def call(env) {
    def serviceName = "application"
    def namespace = "model-serving"
    def deploymentName = env.KUBE_DEPLOYMENT_NAME
    def releaseName = env.HELM_RELEASE_NAME
    def chartPath = env.HELM_CHART_PATH

    // 1. Deploy/Upgrade with Helm
    echo "Deploying/upgrading Helm release '${releaseName}' in namespace '${namespace}'..."
    sh "helm upgrade --install ${releaseName} ${chartPath} --namespace ${namespace}"
    echo "Helm deployment/upgrade complete."

    // 2. Rollout restart
    sh "kubectl rollout restart deployment/${deploymentName} -n ${namespace}"
    sh "kubectl rollout status deployment/${deploymentName} -n ${namespace} --timeout=5m"
    echo "Rollout completed."

    // 3. Wait for external IP
    def externalIp = ""
    def maxAttempts = 20
    def attempt = 0
    while (externalIp == "" && attempt < maxAttempts) {
        attempt++
        try {
            externalIp = sh(script: "kubectl get svc ${serviceName} -n ${namespace} -o jsonpath='{.status.loadBalancer.ingress[0].ip}'", returnStdout: true).trim()
        } catch (e) {
            echo "Attempt ${attempt}: Waiting for external IP..."
        }
        if (externalIp == "") {
            sleep 15
        }
    }

    if (externalIp == "") {
        error "Failed to get external IP for ${serviceName} after ${maxAttempts} attempts."
    }

    echo "External IP: ${externalIp}"

    // 4. Check Swagger
    def swaggerUp = false
    def swaggerAttempts = 10
    def swaggerAttempt = 0

    while (!swaggerUp && swaggerAttempt < swaggerAttempts) {
        swaggerAttempt++
        try {
            def httpCode = sh(script: "curl -s -o /dev/null -w \"%{http_code}\" http://${externalIp}:8000/docs", returnStdout: true).trim()
            if (httpCode == "200") {
                swaggerUp = true
                echo "Swagger is UP!"
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
        error "Swagger never became ready."
    }
}
