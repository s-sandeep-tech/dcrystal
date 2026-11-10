# dcrystal

Start the Docker stack with `./compose.sh up -d --build`. This launcher calculates
the server container's hard memory limit as 60% of the RAM reported by the Docker
engine (the VM allocation on Docker Desktop, or host RAM on Linux). It sets the
same RAM-plus-swap limit to prevent additional swap allocation. Other services
and the external reporting database have separate memory usage.

Use `./compose.sh up -d --build server` to apply server changes, or
`./compose.sh config --quiet` to validate configuration. Direct `docker compose`
commands require `SERVER_MEMORY_LIMIT` in bytes; the launcher recalculates it on
every invocation. The hard limit can cause a container OOM kill if the application
exceeds it; it is not an application memory target.
