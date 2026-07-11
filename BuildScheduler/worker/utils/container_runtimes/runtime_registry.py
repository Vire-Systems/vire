from utils.container_runtimes import (
    docker_runtime
)

RUNTIME_REGISTRY = {
    "docker": docker_runtime.DockerRuntime,
}