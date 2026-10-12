FROM jenkins/jenkins:lts

USER root

# Установка необходимых системных зависимостей для сборки и тестирования OpenBMC
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    ipmitool \
    qemu-system-arm \
    chromium \
    chromium-driver \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Установка Python пакетов для автоматизированного тестирования
RUN pip3 install --no-cache-dir --break-system-packages \
    pytest \
    pytest-html \
    requests \
    selenium \
    locust

# Настройка прав для работы Jenkins
RUN usermod -aG docker jenkins || true

USER jenkins
