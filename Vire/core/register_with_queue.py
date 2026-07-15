"""This module is responsible for registering build data and build state with the Database when a build request is sent."""

from BuildScheduler.Scheduler.db.caching.redis_registry import register_job_with_redis
from BuildScheduler.Scheduler.db.sqlite_orm.crud import create

from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from Vire.core.validate_request import validate_details
from Vire.models.pydantic_classes import BuildRequestModel
from Vire.objects.dataclass_objects.validation_models import ValidatorContext

async def register_build(BRM: BuildRequestModel)-> bool:
    """Register a build with local SQLite database and redis asynchronously."""
    try:
        await register_job_with_redis(BRM, "validating")
        validator_context = ValidatorContext(
            job_uuid=BRM.job_uuid,
            user_uuid=BRM.user_uuid,
            provider=BRM.provider,
            remote_user=BRM.remote_user,
            remote_reponame=BRM.remote_reponame,
            branch=BRM.branch,
            commit_id=BRM.commit_id
        )
        validated_toml = await validate_details(VC=validator_context)
        if not validated_toml:
            await register_job_with_redis(BRM, "failed")
            return False

        await create.register_build_data(BRM, validated_toml)
        await create.register_build_state(job_uuid=BRM.job_uuid, user_uuid=BRM.user_uuid, status="queued")
        await register_job_with_redis(BRM, "passed")
        return True

    except Exception:
        await register_job_with_redis(BRM, "failed")
        await vire_logger("critical", "Registering with SQLite queue failed.")
        return False
