pipeline {
    agent any

    environment {
        // Dynamic app tag based on build number
        application_registry            = 'ngnquanq/demand-forecasting'
        application_tag                  = "v${env.BUILD_NUMBER}-${new Date().format('yyyyMMdd')}"

        jenkins_registry                = 'ngnquanq/custom-jenkins'
        jenkins_tag                     = "1.0.0"

        // Other environment variables
        dockerhub_registryCredentialID  = 'dockerhub'
        HELM_RELEASE_NAME                = 'application'
        HELM_CHART_PATH                  = './helm-charts/application'
        KUBE_CREDENTIAL_ID               = 'gke-kubeconfig'
        KUBE_NAMESPACE                   = 'model-serving'
        KUBE_DEPLOYMENT_NAME             = 'application'
    }

    stages {
        stage('Test') {
            agent {
                docker {
                    image 'python:3.9-slim-buster'// light version
                    args '-u 0'
                }
            }
            steps {
                script {
                    echo '🔍 Running tests with coverage guard…'
                    sh 'apt-get update && apt-get install -y libgomp1'
                    sh 'python --version'
                    sh 'python -m pip install -r requirements.txt'
                    def status = sh(
                        script: 'python -m pytest --cov=src --cov-fail-under=66',
                        returnStatus: true
                    )
                    if (status != 0) {
                        error "❌ Tests failed (exit code: ${status})"
                    }
                    echo '✅ All tests passed'
                }
            }
        }
        
        stage('Build') {
            steps {
                script {
                    echo 'Building Docker image model image...'
                    sh "docker build -t ${application_registry}:${application_tag} ."
                    echo 'Building Docker image jenkins image...'
                    sh "docker build -t ${jenkins_registry}:${jenkins_tag} ./infrastructure/jenkins/" 
                }
            }
        }

        stage('Push') {
            steps {
                script {
                    withCredentials([
                        usernamePassword(
                            credentialsId: 'dockerhub',
                            usernameVariable: 'DOCKER_USER',
                            passwordVariable: 'DOCKER_PASS'
                        )
                    ]) {
                        sh "echo ${DOCKER_PASS} | docker login -u ${DOCKER_USER} --password-stdin"
                        sh "docker push ${application_registry}:${application_tag}"
                        echo '✅ Docker images pushed successfully!'
                    }
                }
            }
        }


        stage('Deploy the main application') {
            agent {
                kubernetes {
                    containerTemplate {
                        name 'helm'
                        image "${jenkins_registry}:${jenkins_tag}" // Your Jenkins/Helm tools image
                        alwaysPullImage true
                    }
                }
            }
            steps {
                script {
                    def deployApp = load 'jenkins/scripts/deployApp.groovy'

                    container('helm') {
                        deployApp(env, "${application_registry}:${application_tag}")
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

                }
            }
        }
        failure {
            script {
                withCredentials([string(credentialsId: 'discord', variable: 'DISCORD_WEBHOOK_URL')]) {
                    discordSend description: 'Build failed! Check Jenkins for details.',
                                 webhookURL: "${DISCORD_WEBHOOK_URL}",
                                 title: 'Deployment Failed'
                }
            }
        }
    }
}