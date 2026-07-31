import asyncio

from BuildScheduler.Scheduler.db.sqlite_orm.crud import update
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.errors.container_runtime_errors import (
    ContainerAdapterAPIError,
    ContainerNotFound,
)
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.shared_state import shared_config
from shared.state_transition import transition_job_state


async def terminate_worker(job_uuid: str)-> None:
    """
    Cancel a job.
    """
    try:
        async with transition_job_state(
            on_exit = "cancelled", on_enter=None, on_error=None,
            state_updater = update.update_job_status,
            job_uuid = job_uuid
        ):
            runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
            await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)

    except (ContainerAdapterAPIError, ContainerNotFound) as e:
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                internal_log="Unexpected error occured while deleting a container (Exception)",
                summary=e.error_title,
                exception_name=str(type(e).__name__),
                source="vire",
            )
        )


async def terminate_workers(job_uuids: list[str]):

    tasks = [
        asyncio.create_task(terminate_worker(job_uuid=j_uuid)) for j_uuid in job_uuids
    ]
    _ = asyncio.gather(*tasks)
