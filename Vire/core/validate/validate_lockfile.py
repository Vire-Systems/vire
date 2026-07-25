"""
This module handles orchestrating the fetch and validation process for the lockfile from data provided when requesting a build.

Functions -
    1. fetch_and_validate_lockfile
"""

from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent
from shared.shared_state import package_managers_list

from shared.errors import validation_errors, vire_errors as errors
from Vire.objects.validation_models import LockfileValidationParams, ValidatorContext
from Vire.core.core_utils.fetch_lockfile import fetch_lockfile_name


async def fetch_and_validate_lockfile(
    LVP: LockfileValidationParams,
    VC: ValidatorContext,
) -> str | None:
    """
    Fetch and validate lockfile against a matrix of supported package managers.

    Args -

        1. LVP - LockfileValidationParams, abbreviation. Core data used for validating the lockfile.
        2. TO - TOMLObjectContext, abbreviation. Dataclass for reading build related toml and general context.
        3. ts - Timestamp
        4. common_line - The common line used in the top validator function.
    """

    # Main logic
    try:
        if LVP.install_req:
            if LVP.package_manager not in package_managers_list:
                raise validation_errors.PackageManagerException()

            lockfile_name = await fetch_lockfile_name(
                username=VC.remote_user,
                reponame=VC.remote_reponame,
                provider=VC.provider,
                commit_id=LVP.commit_id,
                pm=LVP.package_manager,
            )
        else:
            return

        return lockfile_name

    # Exception handling
    except (
        validation_errors.PackageManagerException,
        errors.EmptyLockfileError,
        errors.RepoFileFetchError,
        validation_errors.GitProviderAPIError,
    ) as e:
        await dispatch_event(
            event=ErrorEvent(job_uuid=VC.job_uuid, user_uuid=VC.user_uuid, error=e),
            job_details={
                "Job UUID": VC.job_uuid,
                "Commit SHA": VC.commit_id,
                "Branch Name": VC.branch,
                "PM provided": LVP.package_manager,
            },
        )
