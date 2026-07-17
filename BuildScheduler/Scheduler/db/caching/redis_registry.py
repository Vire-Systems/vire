from typing import Literal

from shared.logging.pub_redis import r as client
from shared.shared_state import shared_config
from Vire.models.pydantic_classes import BuildRequestModel


async def register_job_with_redis(BRM: BuildRequestModel, state: Literal["validating", "passed", "failed"]) -> None:
    async with client as r:
        await r.hset(
            f"job_session:{BRM.user_uuid}/{BRM.job_uuid}",
            mapping={
                "core_id": shared_config.CORE_ID,
                "remote_user": BRM.remote_user,
                "repo": BRM.remote_reponame,
                "commit_id": BRM.commit_id,
                "provider": BRM.provider,
                "state": state,
            },
        )
