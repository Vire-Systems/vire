"""
This module (make_worker) is repsonsible with providing an abstracted function called scheduler_create_worker.
This is made so that the API layer does not mess with fetching raw data, parsing, etc.
"""

from BuildScheduler.Scheduler.db.sqlite_orm.crud import read, update
from BuildScheduler.Scheduler.errors.db_errors import NoJobStateError
from BuildScheduler.Scheduler.manage_worker.create_worker import create_worker_process
from shared.logging.scheduler_logger import vire_logger


async def scheduler_create_worker(job_uuid: str) -> None:
    try:
        job_data = await read.fetch_build_data(job_uuid)
        if not job_data:
            raise NoJobStateError("VC-SC-002")
        vire_logger("info", f"Worker started. Job UUID: {job_uuid}")
        await create_worker_process(job_data)

    except NoJobStateError:
        await update.update_job_status(job_uuid, status_msg="failed", error_code="VC-SC-002")
        return

    except Exception as e:
        await update.update_job_status(job_uuid, status_msg="crashed", error_code="VC-SC=001")
        vire_logger("critical", "[Scheduler scheduler_create_worker] caught broad Exception. Details: %s", e)
