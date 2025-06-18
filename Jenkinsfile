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
    }

    stages {
        //1. Testing

        stage('Test') {
            steps {
            script {
                echo '🔍 Running tests with coverage guard…'
                withPythonEnv('python3') {
                sh 'python -m pip install -r requirements.txt'
                // Run pytest including coverage threshold; capture exit code
                def status = sh(
                    script: 'python -m pytest --cov=src --cov-fail-under=80 ',
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
                    sh 'docker build -t $jenkins_registry ./infrastructure/jenkins/'
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
                    containerTemplate {
                        name 'helm'
                        image 'ngnquanq/custom-jenkins:latest'
                        alwaysPullImage true
                    }
                }
            }
            steps {
                script {
                    container('helm') {
                        def deployApp = load 'jenkins/scripts/deployApp.groovy'
                        deployApp(env)
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
