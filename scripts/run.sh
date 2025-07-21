mkdir -p logs

# Usage ./run.sh <dataset> <project-name> <model_name>
DOCKER_SOCKET=$(docker context inspect | grep '"Host"' | head -n1 | sed -E 's/.*"Host": *"unix:\/\/([^"]+)".*/\1/')

# In a Rootless Docker setup, use `-u 0:0`
# UID:GID on the host is mapped to 0:0 on the container
# See https://forums.docker.com/t/why-is-rootless-docker-still-running-as-root-inside-container/134985
if docker info -f "{{println .SecurityOptions}}" | grep -q rootless; then
    echo "Docker running in rootless mode"
    docker run --rm -it \
    -u 0:0 \
    -v $PWD/vuln_agent:/app/vuln_agent \
    -v $PWD/main.py:/app/main.py \
    -v $PWD/logs:/app/logs \
    -v $PWD/data:/app/data \
    -v $DOCKER_SOCKET:/var/run/docker.sock \
    vuln_agent:latest \
    /bin/bash -c "python main.py --dataset $1 --project $2 --model $3  --verbose"
else
    docker run --rm -it \
    -v $PWD/vuln_agent:/app/vuln_agent \
    -v $PWD/main.py:/app/main.py \
    -v $PWD/logs:/app/logs \
    -v $PWD/data:/app/data \
    -v $DOCKER_SOCKET:/var/run/docker.sock \
    vuln_agent:latest \
    /bin/bash -c "python main.py --dataset $1 --project $2 --model $3  --verbose"

fi