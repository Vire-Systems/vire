"""
This module (create_container_job) handles container creation.

Functions -
1. setup_creation (sync, helper)
2. sync_docker_run (sync, helper)
3. container_create (async, helper)
"""

import asyncio
from textwrap import dedent
import time

from BuildScheduler.shared.container_runtimes.runtime_dc import RuntimeMetadata
from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from BuildScheduler.shared.shared_state import shared_config
from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.utils.state import worker_config
from BuildScheduler.shared.logging.pub_redis import publish_log_redis

from BuildScheduler.worker.schema.errors import ContainerCreationFail, InstallReqMismatch, UnsupportedFramework
from BuildScheduler.shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from BuildScheduler.shared.container_runtimes.base_runtime import ContainerRuntime
from BuildScheduler.worker.utils.adapter import FRAMEWORK_REGISTRY


# Helper
def setup_creation(worker_context: WorkerContext) -> tuple[str, str]:
    """
    Args

    repo_name: Name of the repository.
    framework: Name of the framework.
    package_manager: Name of the package_manager

    Returns

    tuple : (image, cmd)

    Raises worker.schema.errors.UnsupportedFramework if framework_registry.get returns None
    """

    framework_adapter = FRAMEWORK_REGISTRY[worker_context.framework]
    if not framework_adapter:
        raise UnsupportedFramework(f"{worker_context.framework} is not supported.")
    try:
        image = framework_adapter.image

        build_cmd: str = framework_adapter.build_command[worker_context.package_manager]
        checkout = f"git checkout {worker_context.COMMIT_ID}"
        clone = f"git clone {worker_context.remote}"

        cd = f"cd {worker_context.repo_name}"
        clone_and_cd = f"{clone} && {cd}"
        base = f"{clone_and_cd} && {checkout}"

        if worker_context.install_req:
            install_cmd = framework_adapter.install_command[worker_context.package_manager]
            cmd_body = f"{base} && {install_cmd} && {build_cmd}"
        elif not worker_context.install_req:
            cmd_body = f"{base} && {build_cmd}"
        else:
            raise InstallReqMismatch("'install_req' can only be a bool.")

        return image, cmd_body
    except InstallReqMismatch as e:
        raise e
    except Exception as e:
        vire_logger("critical", "[worker setup_creation] Unable to initialize setup. Details: %s", e)
        raise e

async def container_create(worker_context: WorkerContext) -> None:
    """
    Creates a container task and streams the container logs.

    Catches:
        'ContainerCreationFail', 'Exception'.
    """
    try:
        runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()

        # Container creation
        expires_at = int(time.time() + worker_config.CONTAINER_EXPIRY)
        image, cmd_body = setup_creation(worker_context=worker_context)

        if not image or not cmd_body:
            raise ContainerCreationFail(f"{'Image' if not image else 'cmd'} Cannot be none.")
        cmd = ["sh", "-c", cmd_body]

        runtime_metadata = RuntimeMetadata(
            **shared_config.CONTAINER_METADATA,
            expires_at = str(expires_at)
        )

        container_task = asyncio.to_thread(
            runtime.create, 
            job_uuid= worker_context.job_uuid,
            image= image,
            cmd= cmd,
            metadata= runtime_metadata
        )
        await container_task
        container_log_generator = runtime.get_container_log(worker_context.job_uuid)

        for line in container_log_generator:
            str_line = line.decode("utf-8")
            await publish_log_redis(
                str_line,
                user_uuid= worker_context.user_uuid,
                job_uuid=worker_context.job_uuid
            )

    except ContainerCreationFail as e:
        await publish_log_redis(
            line=dedent(
                """
                VC-WK-001. Internal error. 

                Note: Configuration error. If you see this, open an issue on github with a screenshot.
                """),
            user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid
        )
        vire_logger("critical", "Container creation failed. Details: %s", str(e))
    except Exception as e:
        vire_logger(
            "critical", "[container_create] Container creation for job '%s' was unsucessful. Details: %s",
            worker_context.job_uuid, e
        )
