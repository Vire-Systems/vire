"""
This module (del_container) handles delayed container deletion

Functions present-

1. get_container_object (async, helper).
2. delayed_delete_helper (async, helper)
3. delayed_delete (async, main)
"""

import asyncio
from textwrap import dedent

from BuildScheduler.Scheduler.utils import mutex_locks, state
from BuildScheduler.Scheduler.utils.state import scheduler_config
from shared.container_runtimes.errors import ContainerNotFound
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.logging.pub_redis import publish_log_redis
from shared.logging.scheduler_logger import vire_logger
from shared.shared_state import shared_config


# Helper called in delayed_delete
async def delayed_delete_helper(job_uuid: str, user_uuid: str) -> None:
    """Sleeps for 300s (state.CONTAINER_REMOVAL_DELAY) and kills the specified container if it's still alive."""
    await asyncio.sleep(scheduler_config.CONTAINER_REMOVAL_DELAY)  # in seconds
    try:
        try:
            runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
            await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)
            vire_logger(
                "info",
                "[Scheduler delayed_delete_helper] Container process '%s' has been auto deleted. Task exceeded 5m limit.",
                job_uuid,
            )
        except ContainerNotFound:
            return
        await publish_log_redis(
            line=dedent(
                f"""
                INFO: VC-SC-005. Job terminated for exceeding 5 minutes.
                Job UUID: {job_uuid}

                Suggested fixes:
                    1. Check for unoptimized dependencies. Check for that by using 'webpack-bundle-analyzer'.
                    2. Use speed measure plugin (speed-measure-plugin) to find what the bottleneck is.
                """
            ),
            user_uuid=user_uuid,
            job_uuid=job_uuid,
        )
    except Exception as e:
        vire_logger("critical", "[delayed_delete] Removal of container '%s' was unsuccessful. Details: %s", job_uuid, e)


# Gets called in core/create_worker
async def delayed_delete(job_uuid: str, user_uuid: str) -> None:
    """Create a task (asyncio.Task) scheduling the deletion of the container specified by name (job_uuid is name)."""
    task = asyncio.create_task(delayed_delete_helper(job_uuid=job_uuid, user_uuid=user_uuid))
    async with mutex_locks.task_removal_lock:
        state.removal_tasks.add(task)
        task.add_done_callback(state.removal_tasks.discard)
