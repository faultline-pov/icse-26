FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt -y update
RUN apt -y upgrade
RUN apt install -y build-essential
RUN apt install -y software-properties-common

RUN apt install -y cmake wget unzip curl

# We want the latest version of Git. The one in the Ubuntu 20.04 repositories is too old.
RUN add-apt-repository -y ppa:git-core/ppa
RUN apt update
RUN apt install -y git

# Install Docker CLI
RUN apt install -y docker.io
RUN apt install -y docker-buildx
RUN docker buildx install

RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add a non-root user with the same UID and GID as the host user
ARG USER_ID
ARG GROUP_ID
RUN if ! getent group ${GROUP_ID}; then \
    groupadd -g ${GROUP_ID} appuser; \
    fi

RUN if ! getent passwd ${USER_ID}; then \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} appuser; \
    fi

# Ensure 'docker' group exists with the correct GID
RUN if getent group docker > /dev/null; then \
        existing_gid=$(getent group docker | cut -d: -f3); \
        if [ "$existing_gid" != "$DOCKER_GID" ]; then \
            groupmod -g "$DOCKER_GID" docker; \
        fi; \
    else \
        groupadd -g "$DOCKER_GID" docker; \
    fi

RUN mkdir -p /opt/miniconda3 && \
    chown -R ${USER_ID}:${GROUP_ID} /opt/miniconda3

# Set the non-root user as the owner of the /app directory
RUN mkdir -p /app && \
    chown -R ${USER_ID}:${GROUP_ID} /app

# Add non-root user to the docker group
RUN usermod -aG docker appuser

# Switch to the non-root user
USER appuser

WORKDIR /app

ENV PATH="/opt/miniconda3/bin:${PATH}"

# Install Miniconda on x86 or ARM platforms
RUN arch=$(uname -m) && \
    if [ "$arch" = "x86_64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"; \
    elif [ "$arch" = "aarch64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"; \
    else \
    echo "Unsupported architecture: $arch"; \
    exit 1; \
    fi && \
    wget $MINICONDA_URL -O miniconda.sh && \
    mkdir -p /opt/miniconda3 && \
    bash miniconda.sh -b -u -p /opt/miniconda3 && \
    rm -f miniconda.sh

COPY --chown=${USER_ID}:${GROUP_ID} requirements.txt .
RUN pip install -r requirements.txt
