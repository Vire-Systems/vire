"""
The module responsible for all the 'update' operations of the CRUD layer.
"""

from typing import Literal

from sqlalchemy import func
from sqlalchemy.future import select

from BuildScheduler.Scheduler.db.sqlite_orm.db import async_session
from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
from shared.errors import scheduler_errors
from BuildScheduler.Scheduler.utils.queues_locks import job_status_locks


async def update_job_status(
    job_uuid: str,
    status_msg: Literal[
        "queued", "running", "crashed", "finished", "cancelled", "failed", "timed_out"
    ],
    error_code: str | None = None,
    PID: int | None = None,
) -> None:
    """
    CRUD function for updating job status in BuildState table.

    Raises NoJobStateError
    """

    async with job_status_locks[job_uuid]:
        async with async_session() as session:
            async with session.begin():
                query = select(BuildState).where((BuildState.job_uuid == job_uuid))
                result = await session.execute(query)
                job_state = result.scalar_one_or_none()
                if not job_state:
                    raise scheduler_errors.NoJobStateError(
                        error_title=f"Tried to fetch job state for job_uuid {job_uuid}. But returned Null."
                    )

                if error_code:
                    job_state.error = error_code
                if PID:
                    job_state.pid = PID

                job_state.status = status_msg
                job_state.finished_at = func.now()
