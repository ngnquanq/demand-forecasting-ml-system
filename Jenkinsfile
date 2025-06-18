
pipeline {
    agent any
    
    environment {
        application_registry            = 'ngnquanq/demand-forecasting'
        application_tag                  = 'latest'
        jenkins_registry                = 'ngnquanq/custom-jenkins'
        dockerhub_registryCredentialID  = 'dockerhub'
        HELM_RELEASE_NAME                = 'application'
        HELM_CHART_PATH                  = './helm-charts/application'
        KUBE_CREDENTIAL_ID               = 'gke-kubeconfig'
        KUBE_NAMESPACE                   = 'model-serving'
        KUBE_DEPLOYMENT_NAME             = 'application'
    }

    stages {
        stage('Setup') {
            steps {
                script {
                    echo 'Setup scripts for pipeline...'
                    def deployApp = load 'jenkins/scripts/deployApp.groovy'
                    echo "DEBUG: deployApp = ${deployApp}, type = ${deployApp.getClass().getName()}"
                }
            }
        }

        stage('Test') {
            steps {
                script {
                    echo '🔍 Running tests with coverage guard…'
                    withPythonEnv('python3') {
                        sh 'python -m pip install -r requirements.txt'
                        def status = sh(
                            script: 'python -m pytest --cov=src --cov-fail-under=80',
                            returnStatus: true
                        )
                        if (status != 0) {
                            error "❌ Tests failed or coverage below 80% (exit code: ${status})"
                        }
                        echo '✅ All tests passed and coverage ≥ 80%'
                    }
                }
            }
        }

        stage('Build') {
            steps {
                script {
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
                    withCredentials([usernamePassword(
                        credentialsId: 'dockerhub',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh 'docker login -u $DOCKER_USER -p $DOCKER_PASS'
                        sh 'docker tag $application_registry $application_registry:$application_tag'
                        sh 'docker tag $jenkins_registry $jenkins_registry:$application_tag'
                        sh 'docker push $application_registry:$application_tag'
                        sh 'docker push $jenkins_registry:$application_tag'
                        echo 'Docker images pushed successfully!'
                    }
                }
            }
        }

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
                    def deployApp = load 'jenkins/scripts/deployApp.groovy'

                    container('helm') {
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
                }
            }
        }
        failure {
            script {
                withCredentials([string(credentialsId: 'discord', variable: 'DISCORD_WEBHOOK_URL')]) {
                    discordSend description: 'Build failed! Check Jenkins for details.',
                                 webhookURL: "${DISCORD_WEBHOOK_URL}",
                                 title: "Deployment Failed"
                }
            }
        }
    }
}
