"""
This module handles orchestrating the fetch and validation process for the lockfile from data provided when requesting a build.

Functions -
    1. validate_lockfile
"""

from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent
from shared.shared_state import lockfile_matrix, package_managers_list

from shared.errors import validation_errors, vire_errors as errors
from Vire.objects.validation_models import LockfileValidationParams, ValidatorContext


async def validate_lockfile(
    LVP: LockfileValidationParams,
    VC: ValidatorContext,
    lockfile_names: list[str]
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
        inverted_dict = {v: k for k, v in lockfile_matrix.items()}

        expected_lockfile_name = inverted_dict.get(LVP.package_manager)

        if not LVP.install_req:
            return None

        if LVP.package_manager not in package_managers_list:
            raise validation_errors.PackageManagerException()

        if not expected_lockfile_name in lockfile_names:
            raise validation_errors.PackageManagerException(
                error_title= f"Expected lockfile ({expected_lockfile_name}) not found.",
                notes=(f"Expected {LVP.package_manager}'s lockfile ({expected_lockfile_name}).",)
            )

        return expected_lockfile_name

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
                "Lockfile(s)" : ', '.join(lockfile_names)
            },
        )
