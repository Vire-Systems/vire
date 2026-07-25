"""
This module (make_worker) is repsonsible with providing an abstracted function called scheduler_create_worker.
This is made so that the API layer does not mess with fetching raw data, parsing, etc.
"""

from BuildScheduler.Scheduler.db.sqlite_orm.crud import read, update
from BuildScheduler.Scheduler.manage_worker.create_worker import create_worker_process
from shared.errors.scheduler_errors import NoJobStateError
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent


async def scheduler_create_worker(job_uuid: str) -> None:
    try:
        job_data = await read.fetch_build_data(job_uuid)
        if not job_data:
            raise NoJobStateError()
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code="VC-I-WORKER_STARTED",
                severity="info",
                summary="A worker process started.",
                source="scheduler",
                exception_name=None,
                internal_log=None,
            )
        )
        await create_worker_process(job_data)

    except NoJobStateError as e:
        await update.update_job_status(
            job_uuid, status_msg="failed", error_code=e.error_code
        )
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code=e.error_code,
                summary=e.error_title,
                severity=e.severity,
                source="Scheduler",
                exception_name=type(e).__name__,
                internal_log=None,
            )
        )

    except Exception as e:
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                summary="Unexpected error occured when attempting to make a worker process.",
                source="scheduler",
                exception_name=type(e).__name__,
                internal_log=None,
            )
        )
        await update.update_job_status(
            job_uuid, status_msg="crashed", error_code="VC-SC=001"
        )
