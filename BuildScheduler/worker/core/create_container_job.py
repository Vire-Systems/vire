"""
This module (create_container_job) handles container creation.

Functions -
1. setup_creation (sync, helper)
2. sync_docker_run (sync, helper)
3. container_create (async, helper)
"""

import asyncio

from core.stream_redis_log import publish_log_redis, stream_logs
from schema.errors import ContainerCreationFail, InstallReqMismatch, UnsupportedFramework
from utils import state
from utils.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from schema.base_runtime import ContainerRuntime
from utils.adapter import FRAMEWORK_REGISTRY
from utils.vire_logger import cfn_log


# Helper
def setup_creation(repo_name: str, framework: str, package_manager: str) -> tuple[str | None, str | None]:
    """
    Args

    repo_name: Name of the repository.
    framework: Name of the framework.
    package_manager: Name of the package_manager

    Returns

    tuple : (image, cmd)

    Raises worker.schema.errors.UnsupportedFramework if framework_registry.get returns None
    """

    framework_adapter = FRAMEWORK_REGISTRY[framework]
    if not framework_adapter:
        raise UnsupportedFramework(f"{framework} is not supported.")
    try:
        image = framework_adapter.image

        build_cmd: str = framework_adapter.build_command[package_manager]
        checkout = f"git checkout {state.COMMIT_ID}"
        clone = f"git clone {state.remote}"

        cd = f"cd {repo_name}"
        clone_and_cd = f"{clone} && {cd}"
        base = f"{clone_and_cd} && {checkout}"

        if state.install_req:
            install_cmd = framework_adapter.install_command[package_manager]
            cmd_body = f"{base} && {install_cmd} && {build_cmd}"
        elif not state.install_req:
            cmd_body = f"{base} && {build_cmd}"
        else:
            raise InstallReqMismatch("'install_req' can only be a bool.")

        return image, cmd_body
    except InstallReqMismatch as e:
        raise e
    except Exception as e:
        cfn_log("critical", "[worker setup_creation] Unable to initialize setup. Details: %s", e)
        raise e

async def container_create(job_uuid: str) -> None:
    """
    Creates a container task and streams the container logs.

    Catches:
        'ContainerCreationFail', 'Exception'.
    """
    try:
        container_runtime = state.container_runtime
        assert container_runtime

        runtime: ContainerRuntime = RUNTIME_REGISTRY[container_runtime]()
        container_task = asyncio.to_thread(runtime.create, job_uuid)
        await container_task
        await asyncio.to_thread(stream_logs, job_uuid)
    except ContainerCreationFail as e:
        await asyncio.to_thread(publish_log_redis, str(e))
    except Exception as e:
        cfn_log(
            "critical", "[container_create] Container creation for job '%s' was unsucessful. Details: %s", job_uuid, e
        )
