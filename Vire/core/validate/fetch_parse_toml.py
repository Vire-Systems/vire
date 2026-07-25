"""
This module is responsible for fetching and parsing the vire.toml.
Details provided by the user's requested repo, branch and commit SHA.

Functions -
    1. fetch_and_parse_toml
"""

from tomllib import TOMLDecodeError

from shared.errors import validation_errors
from shared.errors import vire_errors as errors
from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent
from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml
from Vire.objects.validation_models import ParsedTOMLObject, ValidatorContext
from Vire.project_manifest.parse_toml import parse_toml


async def fetch_and_parse_toml(VC: ValidatorContext) -> ParsedTOMLObject | None:
    """
    This function fetches and parses vire.toml.

    Args -
        TO - ValidatorContext, Toml object with toml data.

    returns -
        ParsedTOMLObject
    """

    try:
        vire_toml_str = await fetch_vire_toml(
            provider=VC.provider,
            remote_user=VC.remote_user,
            remote_reponame=VC.remote_reponame,
            branch=VC.branch,
        )

        try:
            verified_toml: ParsedTOMLObject = await parse_toml(vire_toml_str)
        except TOMLDecodeError as e:
            raise validation_errors.InvalidTomlSyntaxError from e

        return verified_toml

    except (
        validation_errors.InvalidTomlSyntaxError,
        errors.InvalidBranchError,
        validation_errors.InvalidVireTomlError,
        errors.RepoFileFetchError,
        errors.UnsupportedGitProviderError,
    ) as e:
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
