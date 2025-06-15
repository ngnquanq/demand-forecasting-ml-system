FROM jenkins/jenkins:lts-jdk17
USER root

# Install Docker, kubectl, Helm, Python, and pytest
RUN curl https://get.docker.com > dockerinstall && chmod 777 dockerinstall && ./dockerinstall && \
    # Install kubectl
    curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl && \
    chmod +x ./kubectl && \
    mv ./kubectl /usr/local/bin/kubectl && \
    # Install Helm
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash && \
    # Install Python and pytest using system packages
    apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    # Create virtual environment
    python3 -m venv /opt/venv && \
    # Install pytest in virtual environment
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install pytest && \
    # Make pytest available system-wide
    ln -s /opt/venv/bin/pytest /usr/local/bin/pytest

