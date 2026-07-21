"""
This module handles the orchestration of the functions which fetch and validate the package.json file from a user repository.

Functions -
    1. fetch_and_validate_pkgjson
"""

from shared.errors import vire_errors as errors
from Vire.core.core_utils.fetch_buildreq import fetch_package_json
from Vire.objects.validation_models import PkgJSONValidationParams, ValidatorContext
from shared.errors import validation_errors
from Vire.project_manifest.validator import validate_package_json
from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent


async def fetch_and_validate_pkgjson(VC: ValidatorContext, PJVP: PkgJSONValidationParams) -> bool | None:
    """
    Fetches and validates the package.json from user's repo & branch.

    Args:
        1. VC - Validator context, abbrev. Context provided to 'validate_request'.
        2. PJVP - Package JSON Validation Params, abbrev. Parameters for the function.
    """

    # Main logic
    try:
        package_json_str = await fetch_package_json(
            provider=VC.provider, remote_user=VC.remote_user, remote_reponame=VC.remote_reponame, branch=VC.branch
        )
        await validate_package_json(package_json_str)
        return True

    except (
        validation_errors.InvalidPackageJsonError,
        errors.InvalidBranchError,
        errors.RepoFileFetchError,
        errors.UnsupportedGitProviderError
    ) as e:
        await dispatch_event(
            event=ErrorEvent(job_uuid=VC.job_uuid, user_uuid=VC.user_uuid, error=e),
            job_details = {
                "Job UUID": VC.job_uuid,
                "Commit SHA": VC.commit_id,
                "Branch Name": VC.branch
            }
        )
