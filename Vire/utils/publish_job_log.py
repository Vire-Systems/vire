"""
Commonly used function moved to a module to avoid reuse.

Functions:
    1. publish_job_log
"""

from shared.logging.pub_redis import publish_log_redis
from shared.logging.scheduler_logger import vire_logger
from Vire.objects.dataclass_objects.validation_models import TOMLValidationParams, ValidatorContext


async def publish_job_log(
    line: str,
    error_code: str,
    job_uuid=ValidatorContext.job_uuid,
    user_uuid=ValidatorContext.user_uuid,
    ts=TOMLValidationParams.ts,
) -> None:
    """
    Publishes a line using redis streams and logs the error code using vire_logger
    """
    # TODO: Add postgres status updation here.
    await publish_log_redis(line=f"{ts} : {line}", user_uuid=user_uuid, job_uuid=job_uuid)
    vire_logger("info", f"Error code: '{error_code}' for job_uuid: '{job_uuid}'")
