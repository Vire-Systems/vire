"""
The module responsible for all the 'create' operations of the CRUD layer.
"""

from typing import Literal

from BuildScheduler.Scheduler.db.sqlite_orm.db import async_session
from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildData, BuildState
from Vire.models.pydantic_classes import BuildRequestModel
from Vire.objects.validation_models import ParsedTOMLObject


async def register_build_data(BRM: BuildRequestModel, PTO: ParsedTOMLObject) -> None:
    """
    CRUD function for registering a build's data in the local DB.

    Args:
    -----
    - BRM: Build Request Model, abbrev. The pydantic class
    - PTO: Parsed Vire toml object.
    """
    async with async_session() as session:
        async with session.begin():
            new_build_data = BuildData(
                job_uuid=BRM.job_uuid,
                user_uuid=BRM.user_uuid,
                remote_link=BRM.remote_link,
                commit_id=BRM.commit_id,
                repo_name=BRM.remote_reponame,
                framework=PTO.framework,
                pm=PTO.package_manager,
                install_req=PTO.install_req,
                output_dir=PTO.output_dir,
            )
            session.add(new_build_data)


async def register_build_state(
    job_uuid: str,
    user_uuid: str,
    status: Literal["queued", "running", "crashed", "finished", "cancelled"],
) -> None:
    """
    CRUD function for registering the build's state into the local DB.
    """
    async with async_session() as session:
        async with session.begin():
            new_build_state = BuildState(
                job_uuid=job_uuid, user_uuid=user_uuid, status=status
            )
            session.add(new_build_state)
