"""
This module is responsible for orchestrating the validation of vire.toml file fetched from the user's repository.

Functions -
    1. validate_vire_toml
"""

from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent
from Vire.objects.validation_models import (
    ParsedTOMLObject,
    TOMLValidationParams,
    ValidatorContext,
)
from shared.errors import validation_errors
from Vire.project_manifest.validator import validate_toml


async def validate_vire_toml(
    TVP: TOMLValidationParams, VC: ValidatorContext, PTO: ParsedTOMLObject
) -> bool | None:
    """
    Validates vire.toml fetched from the user's repo.

    Args -
        1. TVP - TOMLValidationParams, abbrev. Data needed to validate the validation process.
        2. VC - ValidatorContext, abbrev. The full context given to validate_request.
        3. PTO - ParsedTomlObject, abbrev. The data returned after the said vire.toml is parsed.
    """

    # Main logic
    try:
        await validate_toml(
            lockfile_name=TVP.lockfile_name,
            package_manager=PTO.package_manager,
            output_dir=PTO.output_dir,
            framework=PTO.framework,
        )
        return True

    # Error handling
    except (
        validation_errors.UnsupportedFrameworkError,
        validation_errors.InvalidOutDirError,
        validation_errors.PackageManagerException,
    ) as e:
        await dispatch_event(
            event=ErrorEvent(job_uuid=VC.job_uuid, user_uuid=VC.user_uuid, error=e),
            job_details={
                "Job UUID": VC.job_uuid,
                "Commit SHA": VC.commit_id,
                "Branch Name": VC.branch,
                "Package Manager": PTO.package_manager,
                "Fetched from": TVP.common_line,
                "Output Directory": PTO.output_dir,
            },
        )
