"""
This module (build_req) contains the router for handling the build requests.

Functions -
    process_build_req (async, fastapi router)
"""

from fastapi import APIRouter

from shared.event_handling.handler import dispatch_event
from shared.events.events import InfoEvent, LogEvent
from Vire.api.router_models.build import BuildReqResponse
from Vire.core.register_with_queue import register_build
from Vire.models.pydantic_classes import BuildRequestModel

router = APIRouter()


@router.post(
    path="/build/build_request",
    response_model=BuildReqResponse,
    operation_id="process_build_request",
)
async def process_build_request(build_request_model: BuildRequestModel):
    """Processes build requests from Middleware microservice."""
    brm = build_request_model  # I can't type BuildRequestModel everytime, so this.
    try:
        result: bool = await register_build(brm)
        status = "PASSED" if result else "FAILED"
        info_line = f"Data validation {status.lower()}."
        status_code = f"VC-I-VALIDATION_{status}"

        await dispatch_event(
            event=InfoEvent(
                job_uuid=brm.job_uuid,
                user_uuid=brm.user_uuid,
                diag_code=status_code,
                summary=info_line,
            ),
            job_details={
                "Job UUID": brm.job_uuid,
                "Git Provider": brm.provider.capitalize(),
                "Commit SHA": brm.commit_id,
                f"{brm.provider.capitalize()} Username": brm.remote_user,
                f"{brm.provider.capitalize()} Repository": brm.remote_reponame,
            },
        )

        return BuildReqResponse(
            success=result,
            reason=f"server {'accepted' if result else 'refused'} the request.",
        )
    except Exception as e:
        await dispatch_event(
            event=LogEvent(
                user_uuid=build_request_model.user_uuid,
                job_uuid=build_request_model.job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                summary="Build Request endpoint raised an unexpected error.",
                source="Vire",
                exception_name=type(e).__name__,
                internal_log=None,
            )
        )
