"""
This module contains the router for handling the cancellation of running/queued build requests.

Functions -
    cancel_build_req (async, fastapi router)
"""

from fastapi import APIRouter

from BuildScheduler.shared.pub_redis import publish_log_redis
from Vire.core.cancel_build_req import terminate_workers
from Vire.models.pydantic_classes import BuildCancelModel
from BuildScheduler.Scheduler.db.sqlite_orm.crud import read

router = APIRouter()

@router.post("/build/cancel_build")
async def cancel_build_req(BCM: BuildCancelModel):
    try:
        for job_uuid in BCM.job_uuids:
            data = await read.fetch_build_data(job_uuid=job_uuid)
            if not data:
                return {"success": False, "reason": "Job State fetch unsuccessful."}
    
            if not data.user_uuid == BCM.user_uuid:
                return {"success": False}
            await publish_log_redis(f"Jobs {BCM.job_uuids} cancelled.", BCM.user_uuid, job_uuid)

        await terminate_workers(job_uuids=BCM.job_uuids)
        
        return {"success": True}
    except Exception:
        return {"success": False}