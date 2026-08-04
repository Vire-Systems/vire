"""The core module providing functions used for dispatching queued jobs."""

import asyncio

from BuildScheduler.Scheduler.core.make_worker import scheduler_create_worker
from BuildScheduler.Scheduler.utils import queues, mutex_locks
from shared.container_runtimes.runtime_dc import RuntimeMetadata
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.errors.container_runtime_errors import ContainerAdapterAPIError
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.shared_state import shared_config


async def get_worker_count(fetch_all: bool = False) -> int | None:
    """
    Fetch active worker count from container runtime.

    Args:
    -----
    - fetch_all - Returns all containers including the dead / finished ones.

    Raises:
    -------
    - ValueError if the count of managed containers is not an '`int`'.
    """
    try:
        runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()

        metadata = RuntimeMetadata(**shared_config.CONTAINER_METADATA, expires_at=None)
        count_managed_containers = await runtime.list_managed_containers(
            metadata, count=True, all=fetch_all
        )
        if not isinstance(count_managed_containers, int):
            raise ValueError(
                f"The value of count_managed_containers is invalid. {count_managed_containers=}"
            )

        return count_managed_containers

    except ValueError:
        raise

    except ContainerAdapterAPIError as e:
        await dispatch_event(
            LogEvent(
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                internal_log="Unexpected error occured while getting container count (Exception)",
                summary=e.error_title,
                exception_name=str(type(e).__name__),
                source="scheduler",
            )
        )


async def launch_workers(job_uuids: list[str]) -> None:
    """Launch the same number of workers as the number of elements in job_uuids."""
    task_list: list[asyncio.Task[None]] = []

    for job_uuid in job_uuids:
        task_list.append(asyncio.create_task(scheduler_create_worker(job_uuid)))
    _ = await asyncio.gather(*task_list)


async def dispatch_queued_job(
    available_slots: int,
) -> None:
    """
    Dispatch the number of jobs (available_slots) which are queued in SQLite DB.

    Args:
    -----
    - available_slots: Number of worker slots available.
    """
    if available_slots <= 0:
        return

    async with mutex_locks.scheduler_lock:
        job_uuids: list[str] = []
        for _ in range(available_slots):
            try:
                job_uuid: str = queues.db_build_queue.get_nowait()
                job_uuids.append(job_uuid)
            except asyncio.QueueEmpty:
                break

    await launch_workers(job_uuids=job_uuids)
