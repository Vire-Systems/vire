"""
This module contains the router for handling the cancellation of running/queued build requests.

Functions -
    cancel_build_req (async, fastapi router)
"""

from fastapi import APIRouter

from BuildScheduler.Scheduler.db.sqlite_orm.crud import read
from shared.event_handling.handler import dispatch_event
from shared.events.events import InfoEvent
from Vire.api.router_models.build import CancelBuildResponse
from Vire.core.cancel_build_req import terminate_workers
from Vire.models.pydantic_classes import BuildCancelModel

router = APIRouter()


@router.post("/build/cancel_build")
async def cancel_build_req(BCM: BuildCancelModel):
    try:
        for job_uuid in BCM.job_uuids:
            data = await read.fetch_build_data(job_uuid=job_uuid)
            success = False
            if data and data.user_uuid == BCM.user_uuid:
                success = True

            await dispatch_event(event=InfoEvent(
                job_uuid = f"{', '.join(BCM.job_uuids)}",
                user_uuid = BCM.user_uuid,
                diag_code = f"VC-I-CANCELLATION_{'SUCCESS' if success else 'FAILED'}",
                summary = f"Cancellation of build(s) {'successful' if success else 'failed'}."
            ))

        await terminate_workers(job_uuids=BCM.job_uuids)

        return CancelBuildResponse(success=True)
    except Exception:
        return CancelBuildResponse(success=False)
