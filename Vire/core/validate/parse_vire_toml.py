"""
This module is responsible for fetching and parsing the vire.toml.
Details provided by the user's requested repo, branch and commit SHA.

Function(s):
----------
1. parse_vire_toml
"""

from tomllib import TOMLDecodeError

from shared.errors import validation_errors
from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent
from Vire.objects.validation_models import ParsedTOMLObject, ValidatorContext
from Vire.project_manifest.parse_toml import parse_toml


async def parse_vire_toml(VC: ValidatorContext, vire_toml_str: str) -> ParsedTOMLObject | None:
    """
    This function fetches and parses vire.toml.

    Args:
    -----
    - VC: ValidatorContext
    - Toml object with toml data.

    Returns:
    --------
    - ParsedTOMLObject
    """

    try:
        try:
            verified_toml: ParsedTOMLObject = await parse_toml(vire_toml_str)
        except TOMLDecodeError as e:
            raise validation_errors.InvalidTomlSyntaxError from e

        return verified_toml

    except validation_errors.InvalidTomlSyntaxError as e:
        await dispatch_event(
            event=ErrorEvent(job_uuid=VC.job_uuid, user_uuid=VC.user_uuid, error=e),
            job_details={
                "Job UUID": VC.job_uuid,
                "Commit SHA": VC.commit_id,
                "Provider": VC.provider.capitalize(),
                "Branch Name": VC.branch,
                "Fetched from": f"Root Directory of {VC.branch}, {VC.remote_reponame}",
            },
        )
