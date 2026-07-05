"""
This module (build_req) contains the router for handling the build requests.

Functions -
    process_build_req (async, fastapi router)
"""

import traceback
from fastapi import APIRouter

from Vire.core.register_with_queue import register_build
from Vire.models.pydantic_classes import BuildRequestModel
from Vire.api.router_models.build import BuildReqResponse

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
        reason = "Server accepted the request." if result else "Server refused the request."

        return BuildReqResponse(success=result, reason=reason)
    except Exception:
        traceback.print_exc()
