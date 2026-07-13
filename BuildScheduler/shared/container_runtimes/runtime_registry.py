from BuildScheduler.shared.container_runtimes.base_runtime import ContainerRuntime
from BuildScheduler.shared.container_runtimes.runtimes import (
    docker_runtime
)

RUNTIME_REGISTRY : dict[str, type[ContainerRuntime]] = {
    "docker": docker_runtime.DockerRuntime,
}