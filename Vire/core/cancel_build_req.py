
import asyncio

from docker.models.containers import Container

from BuildScheduler.Scheduler.db.sqlite_orm.crud import update
from BuildScheduler.Scheduler.manage_worker.del_container import get_container_object
from BuildScheduler.shared.scheduler_logger import vire_logger
from BuildScheduler.Scheduler.utils.state import docker_client as client

async def terminate_worker(job_uuid: str):

    container_obj: Container | None = await get_container_object(job_uuid, client)
    if not container_obj:
        await vire_logger("info", "[terminate_worker] Could not fetch container object for job uuid: '%s'", job_uuid)
        return

    await update.update_job_status(job_uuid=job_uuid, status_msg="cancelled")
    await vire_logger("info", "[terminate_worker] Job UUID: '%s' has been cancelled.", job_uuid)

    await asyncio.to_thread(container_obj.remove,force=True)


async def terminate_workers(job_uuids: list[str]):

    tasks = [asyncio.create_task(terminate_worker(job_uuid=j_uuid)) for j_uuid in job_uuids]
    asyncio.gather(*tasks)