"""
The module providing an abstracted function called scheduler_create_worker.
This is made so that the API layer does not mess with fetching raw data, parsing, etc.
"""

from BuildScheduler.Scheduler.db.sqlite_orm.crud import read, update
from BuildScheduler.Scheduler.manage_worker.create_worker import create_worker_process
from shared.errors.scheduler_errors import NoJobStateError
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.state_transition import transition_job_state


async def _create_helper(job_uuid: str) -> None:
    """
    The helper used for creating a worker process.

    Raises:
    ------
    - NoJobStateError: if job data is '`None`'.
    - Exceptions (all other errors that might occur)
    """
    async with transition_job_state(
        on_enter=None,
        on_exit=None,
        on_error="crashed",
        state_updater=update.update_job_status,
        job_uuid=job_uuid,
    ):
        job_data = await read.fetch_build_data(job_uuid)

        if job_data is None:
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


async def scheduler_create_worker(job_uuid: str) -> None:
    try:
        await _create_helper(job_uuid)

    except (NoJobStateError, Exception) as e:
        default = "Unexpected error occured when attempting to make a worker process."
        await dispatch_event(
            event=LogEvent(
                job_uuid=job_uuid,
                diag_code=getattr(e, "error_code", "VC-IN-UNEXPECTED_INTERNAL_ERROR"),
                severity=getattr(e, "severity", "critical"),
                summary=getattr(e, "error_title", default),
                source="scheduler",
                exception_name=type(e).__name__,
                internal_log=None,
            )
        )
