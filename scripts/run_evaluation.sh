# Usage ./run.sh <dataset-name> <project-name> [openhands]
DOCKER_SOCKET=$(docker context inspect | grep '"Host"' | head -n1 | sed -E 's/.*"Host": *"unix:\/\/([^"]+)".*/\1/')

# Default value for dataset is "cwe-bench-java", otherwise use $1 if provided
if [ -z "$1" ]; then
    echo "No dataset provided, using default value 'cwe-bench-java'"
    dataset="cwe-bench-java"
else
    echo "Dataset provided: $1"
    dataset="$1"
fi
# Default value for $filter is "*", otherwise use $2 if provided
if [ -z "$2" ]; then
    echo "No filter provided, using default value '*'"
    # We want the actual asterisk, not a directory listing
    filter="*"
else
    echo "Filter provided: $2"
    filter="$2"
fi
# Check if the third argument is "openhands"
if [ "$3" == "openhands" ]; then
    echo "OpenHands evaluation requested"
    openhands="--openhands"
else
    echo "OpenHands evaluation not requested"
    openhands=""
fi
# In a Rootless Docker setup, use `-u 0:0`
# UID:GID on the host is mapped to 0:0 on the container
# See https://forums.docker.com/t/why-is-rootless-docker-still-running-as-root-inside-container/134985
docker run --rm -it \
    -v $PWD/vuln_agent:/app/vuln_agent \
    -v $PWD/evaluate.py:/app/evaluate.py \
    -v $PWD/logs:/app/logs \
    -v $PWD/openhands_logs:/app/openhands_logs \
    -v $PWD/data:/app/data \
    -v $DOCKER_SOCKET:/var/run/docker.sock \
    vuln_agent:latest \
    /bin/bash -c "python evaluate.py --dataset $dataset --filter '$filter' '$openhands'"