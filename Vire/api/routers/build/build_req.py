"""
This module (build_req) contains the router for handling the build requests.

Functions -
    process_build_req (async, fastapi router)
"""

from textwrap import dedent
from fastapi import APIRouter

from Vire.core.register_with_queue import register_build
from Vire.models.pydantic_classes import BuildRequestModel
from Vire.api.router_models.build import BuildReqResponse
from BuildScheduler.shared.pub_redis import publish_log_redis

router = APIRouter()

@router.post(
    path="/build/build_request",
    response_model=BuildReqResponse,
    operation_id="process_build_request"
)
async def process_build_request(build_request_model: BuildRequestModel):
    """Processes build requests from Middleware microservice."""
    brm = build_request_model # I can't type BuildRequestModel everytime, so this.
    try:
        result: bool = await register_build(brm)
        info_line = f"Data validation {'successful' if result else 'failed'}."
        final_line = ("Build has been successfully queued." if result else "Reason for Failure provided below.")
        await publish_log_redis(
            line= dedent(
            f"""
            Info: {info_line}

            Job Data:
                Job UUID: {brm.job_uuid}
                Git Provider: {brm.provider.capitalize()}
                Commit SHA: {brm.commit_id}
                {brm.provider.capitalize()} Username: {brm.remote_user}
                {brm.provider.capitalize()} Repository: {brm.remote_reponame}

            {final_line}
            """),
            user_uuid = build_request_model.user_uuid, job_uuid = build_request_model.job_uuid
        )    

        return BuildReqResponse(
            success=result, 
            reason=f"server {'accepted' if result else 'refused'} the request.")
    except Exception:
        await publish_log_redis(
            line= dedent(
            """
            Error: VC-VD-001. Unexpected internal error.

            Validation failed due to an internal error. Contact us if you see this.
            """),
            user_uuid = build_request_model.user_uuid, job_uuid = build_request_model.job_uuid
        )
