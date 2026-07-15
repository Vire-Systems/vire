"""The utility module used for dispatching queued jobs."""

from typing import Literal
import asyncio

from BuildScheduler.Scheduler.core.core_utilities.make_worker import scheduler_create_worker
from BuildScheduler.Scheduler.utils import queues_locks
from BuildScheduler.shared.container_runtimes.runtime_dc import RuntimeMetadata
from BuildScheduler.shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from BuildScheduler.shared.shared_state import shared_config


async def get_worker_count(fetch_all = False)-> int:
    """
    Fetch active worker count from docker API.

    Args:
    -----
        fetch_all - Returns all containers including the dead / finished ones.
    """
    runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()

    metadata = RuntimeMetadata(
        **shared_config.CONTAINER_METADATA,
        expires_at = None
    )
    count_managed_containers = await runtime.list_managed_containers(metadata, count=True)
    if not isinstance(count_managed_containers, int):
        raise ValueError(f"The value of count_managed_containers is invalid. {count_managed_containers=}")
    return count_managed_containers


async def launch_workers(job_uuids: list[str])-> None:
    """Launch the same number of workers as the length of job_uuids."""
    task_list: list[asyncio.Task[None]] = []

    for job_uuid in job_uuids:
        task_list.append(asyncio.create_task(scheduler_create_worker(job_uuid)))
    await asyncio.gather(*task_list)


async def dispatch_queued_job(available_slots: int)-> Literal["queued", "started"] | None:
    """
    Dispatch the number of jobs (available_slots) which are queued in SQLite DB.
    """
    if available_slots <= 0:
        return

    async with queues_locks.scheduler_lock:
        job_uuids: list[str] = []
        for _ in range(available_slots):
            try:
                job_uuid = queues_locks.db_build_queue.get_nowait()
                job_uuids.append(job_uuid)
            except asyncio.QueueEmpty:
                if len(job_uuids) != 0:
                    vire_logger("info",
                        "Not enough queued processes to spawn. Available slots: %i. Number of spawned processes: %i",
                        available_slots, len(job_uuids)
                    )
                break
    await launch_workers(job_uuids=job_uuids)