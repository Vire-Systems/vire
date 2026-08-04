"""
The module responsible for all the 'read' operations of the CRUD layer.
"""

from sqlalchemy.future import select

from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams
from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildData, BuildState
from BuildScheduler.Scheduler.db.sqlite_orm.db import async_session
from BuildScheduler.Scheduler.utils.mutex_locks import queue_insert_lock
from BuildScheduler.Scheduler.utils.queues import db_build_queue

async def fetch_build_data(job_uuid: str) -> WorkerCreationParams | None:
    """
    Fetches full details of a build based on job_uuid.
    """
    async with async_session() as session:
        query = select(BuildData).where(BuildData.job_uuid == job_uuid)
        result = await session.execute(query)
        build_data_obj: BuildData | None = result.scalar_one_or_none()
        if build_data_obj is not None:
            data_obj = WorkerCreationParams(
                job_uuid=build_data_obj.job_uuid,
                user_uuid=build_data_obj.user_uuid,
                remote_link=build_data_obj.remote_link,
                commit_id=build_data_obj.commit_id,
                repo_name=build_data_obj.repo_name,
                framework=build_data_obj.framework,
                pm=build_data_obj.pm,
                install_req=build_data_obj.install_req,
                output_dir=build_data_obj.output_dir,
            )
            return data_obj
        else:
            return None


async def load_queued_builds(number_of_builds: int) -> None:
    """
    crud's read function for fetching builds where the build status is 'queued'.

    Args:
    -----
    - number_of_buids - The number of queued functions to fetch from the db.

    Behavior:
    - Fetches all builds with status = 'queued'. Then puts them into an asyncio.Queue.
    """
    async with queue_insert_lock:
        async with async_session() as session:
            query = (
                select(BuildState)
                .where(BuildState.status == "queued")
                .limit(number_of_builds)
            )
            result = await session.execute(query)
            queued_builds = result.scalars().all()

            for build_obj in queued_builds:
                await db_build_queue.put(build_obj.job_uuid)
