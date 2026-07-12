from BuildScheduler.shared.container_runtimes.runtimes import (
    docker_runtime
)

RUNTIME_REGISTRY = {
    "docker": docker_runtime.DockerRuntime,
}