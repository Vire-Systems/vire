import asyncio

from BuildScheduler.Scheduler.db.sqlite_orm.crud import update
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.logging.scheduler_logger import vire_logger
from shared.shared_state import shared_config


async def terminate_worker(job_uuid: str):

    runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()

    await update.update_job_status(job_uuid=job_uuid, status_msg="cancelled")
    vire_logger("info", "[terminate_worker] Job UUID: '%s' has been cancelled.", job_uuid)

    await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)


async def terminate_workers(job_uuids: list[str]):

    tasks = [asyncio.create_task(terminate_worker(job_uuid=j_uuid)) for j_uuid in job_uuids]
    asyncio.gather(*tasks)
