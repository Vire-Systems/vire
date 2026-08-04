"""
This module (del_container) handles delayed container deletion

Functions present-

1. get_container_object (async, helper).
2. delayed_delete_helper (async, helper)
3. delayed_delete (async, main)
"""

import asyncio

from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
from BuildScheduler.Scheduler.utils import mutex_locks, state
from BuildScheduler.Scheduler.utils.state import scheduler_config
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.errors.container_runtime_errors import (
    ContainerAdapterAPIError,
    ContainerNotFound,
)
from shared.event_handling.handler import dispatch_event
from shared.events.events import ContainerTimeoutEvent, LogEvent
from shared.shared_state import shared_config
from shared.state_transition import transition_job_state


# Helper called in delayed_delete
async def delayed_delete_helper(job_uuid: str, user_uuid: str) -> None:
    """Sleeps for <state.CONTAINER_REMOVAL_DELAY> and kills the specified container if it's still alive."""
    await asyncio.sleep(scheduler_config.CONTAINER_REMOVAL_DELAY)  # in seconds
    try:
        async with transition_job_state(
            on_enter=None,
            on_exit="timed_out",
            on_error=None,
            state_updater=update_job_status,
            job_uuid=job_uuid,
        ):
            try:
                runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
                await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)

            except ContainerNotFound:
                raise

            await dispatch_event(
                event=ContainerTimeoutEvent(
                    job_uuid=job_uuid,
                    user_uuid=user_uuid,
                    summary=f"Container timed out. Timeout delay: {scheduler_config.CONTAINER_REMOVAL_DELAY}s.",
                )
            )

    except ContainerNotFound:
        pass  # Worker autocollected its container. It doesn't exist anymore.

    except (ContainerAdapterAPIError, Exception) as e:
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                exception_name=type(e).__name__,
                summary="Removal of container was unsuccessful",
                internal_log= "Unexpected error occured while deleting a container (Exception)",
                source="scheduler",
            )
        )


async def delayed_delete(job_uuid: str, user_uuid: str) -> None:
    """Create a task (asyncio.Task) scheduling the deletion of the container specified by name (job_uuid is name)."""
    task = asyncio.create_task(
        delayed_delete_helper(job_uuid=job_uuid, user_uuid=user_uuid)
    )
    async with mutex_locks.task_removal_lock:
        state.removal_tasks.add(task)
        task.add_done_callback(state.removal_tasks.discard)
