"""
This module (cleanup_container) handles container removal.

Functions -
1. remove_container (sync)

"""

from textwrap import dedent

from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.shared.container_runtimes.base_runtime import ContainerRuntime
from BuildScheduler.shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from BuildScheduler.worker.utils.state import worker_config
from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from BuildScheduler.shared.logging.pub_redis import publish_log_redis
from BuildScheduler.worker.resolve_worker_state import update_job_state

async def remove_container(worker_context: WorkerContext):
    """Name (UUID4 used for naming) based container remover"""
    try:
        runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()
        runtime.remove(worker_context.job_uuid)

    except KeyError:
        vire_logger("critical", "The container runtime class for '%s' doesn't exist. VC-VD-00", worker_config.CONTAINER_RUNTIME)
        await publish_log_redis(line=dedent(
            """
            Error: VC-WK-001. Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.

            Cause: Configuration error
            """
        ), job_uuid=worker_context.job_uuid, user_uuid=worker_context.user_uuid) 
        update_job_state(
            job_uuid= worker_context.job_uuid,
            status= "finished",
            prev_status="running"
        )

    except Exception:
        raise
