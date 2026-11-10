#!/bin/sh
# Resolve a percentage on the Docker host (also correct for Docker Desktop/remote engines).
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
docker_memory_bytes=$(docker info --format '{{.MemTotal}}')
case "$docker_memory_bytes" in
    ''|*[!0-9]*|0) echo 'Cannot determine Docker engine memory.' >&2; exit 1 ;;
esac
SERVER_MEMORY_LIMIT=$((docker_memory_bytes * 60 / 100))
export SERVER_MEMORY_LIMIT
exec docker compose "$@"
