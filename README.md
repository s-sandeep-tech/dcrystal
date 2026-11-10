# dcrystal

Start the Docker stack with `docker compose up -d --build`. To rebuild only the
server, use `docker compose up -d --build server`. No memory environment variable
is required. The server defaults to a hard limit of 10,059,718,656 bytes, exactly
60% of the deployment host's reported 16,766,197,760 bytes of Docker-engine RAM.
The RAM-plus-swap limit is the same, preventing additional swap allocation.
Other services and the external reporting database have separate memory usage.

Use `docker compose config --quiet` to validate configuration. If Docker-engine
RAM changes or you deploy elsewhere, use `./compose.sh up -d --build server` to
recalculate 60% for that host, or update the Compose default. An explicitly set
`SERVER_MEMORY_LIMIT` overrides the default. The hard limit can cause a container
OOM kill if the application exceeds it; it is not an application memory target.
