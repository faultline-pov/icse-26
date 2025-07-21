DOCKER_SOCKET=$(docker context inspect | grep '"Host"' | head -n1 | sed -E 's/.*"Host": *"unix:\/\/([^"]+)".*/\1/')
docker build --build-arg USER_ID=$(id -u) \
             --build-arg GROUP_ID=$(id -g) \
             --build-arg DOCKER_GID=$(stat -c '%g' $DOCKER_SOCKET) \
             -t vuln_agent:latest .