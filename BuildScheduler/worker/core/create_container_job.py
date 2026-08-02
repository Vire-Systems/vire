"""
This module (create_container_job) handles container creation.

Functions -
1. setup_creation (sync, helper)
2. container_create (async, helper)
"""

import asyncio
import time

from shared.errors.container_runtime_errors import ContainerCreationFail
from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY
from BuildScheduler.worker.utils.state import worker_config

from shared.container_runtimes.base_runtime import ContainerRuntime
from shared.container_runtimes.runtime_dc import RuntimeMetadata
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY

from shared.logging.pub_redis import publish_log_redis
from shared.shared_state import shared_config

from shared.events.events import LogEvent
from shared.event_handling.handler import dispatch_event


# Helper
def setup_creation(worker_context: WorkerContext) -> tuple[str, str]:
    """
    Args

    repo_name: Name of the repository.
    framework: Name of the framework.
    package_manager: Name of the package_manager

    Returns

    tuple : (image, cmd)

    Raises:
    ---
    UnsupportedFramework if framework_registry.get returns None
    """

    framework_adapter = FRAMEWORK_REGISTRY[worker_context.framework]
    try:
        image = framework_adapter.image

        build_cmd: str = framework_adapter.build_command[worker_context.package_manager]
        checkout = f"git checkout {worker_context.COMMIT_ID}"
        clone = f"git clone {worker_context.remote}"

        cd = f"cd {worker_context.repo_name}"
        clone_and_cd = f"{clone} && {cd}"
        base = f"{clone_and_cd} && {checkout}"

        if worker_context.install_req is True:
            install_cmd = framework_adapter.install_command[
                worker_context.package_manager
            ]
            cmd_body = f"{base} && {install_cmd} && {build_cmd}"
        else:
            cmd_body = f"{base} && {build_cmd}"

        return image, cmd_body
    except Exception:
        raise


async def container_create(worker_context: WorkerContext) -> None:
    """
    Creates a container task and streams the container logs.

    Raises:
    -------
    - ContainerCreationFail
    - Exception (aka all errors)
    """

    runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()

    # Container creation
    expires_at = int(time.time() + worker_config.CONTAINER_EXPIRY)
    image, cmd_body = setup_creation(worker_context=worker_context)

    if (not image) or (not cmd_body):
        raise ContainerCreationFail(
            error_title="Creation of the isolated environment failed."
        )
    cmd = ["sh", "-c", cmd_body]

    runtime_metadata = RuntimeMetadata(
        **shared_config.CONTAINER_METADATA, expires_at=str(expires_at)
    )

    await asyncio.to_thread(
        runtime.create,
        job_uuid=worker_context.job_uuid,
        image=image,
        cmd=cmd,
        metadata=runtime_metadata,
    )
    container_log_generator = runtime.get_container_log(worker_context.job_uuid)

    for line in container_log_generator:
        str_line = line.decode("utf-8")
        await publish_log_redis(
            str_line,
            user_uuid=worker_context.user_uuid,
            job_uuid=worker_context.job_uuid,
        )
