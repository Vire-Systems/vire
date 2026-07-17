"""
This module is responsible for orchestrating the validation of vire.toml file fetched from the user's repository.

Functions -
    1. validate_vire_toml
"""

from textwrap import dedent

from shared.shared_state import lockfile_matrix
from Vire.objects.dataclass_objects.validation_models import ParsedTOMLObject, TOMLValidationParams, ValidatorContext
from Vire.project_manifest.errors import config_errors
from Vire.project_manifest.validator import validate_toml
from Vire.utils.publish_job_log import publish_job_log


async def validate_vire_toml(TVP: TOMLValidationParams, VC: ValidatorContext, PTO: ParsedTOMLObject) -> bool | None:
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
    except config_errors.UnsupportedFrameworkError as e:
        await publish_job_log(
            dedent(
                f"""
            Error: VC-VD-021. Unable to validate vire.toml.
            Timestamp: {TVP.ts}

            Details:
                Job UUID: {VC.job_uuid}
                vire.toml: {TVP.common_line}
                Issue: {str(e)}

            Suggested fixes:
                1. Upload file in HTML.
                2. Try other supported frameworks available in docs.
            """
            ),
            error_code="VC-VD-021",
        )

    except config_errors.PackageManagerException as e:
        expected_pm = lockfile_matrix[TVP.lockfile_name] if TVP.lockfile_name else "Unsupported PM"
        await publish_job_log(
            dedent(
                f"""
            Error: VC-VD-022. PM and lockfile do not match.
            Timestamp: {TVP.ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: {TVP.common_line}

            Errors caused by:
                Lockfile: {TVP.lockfile_name} (from {VC.remote_reponame} repository.)
                Expected PM: {expected_pm} (Based on lockfile.)
                Provided PM: {PTO.package_manager} (from vire.toml)
                Issue: {str(e)}

            Suggested fixes:
                1. Run npm install and commit the lockfile and delete the old one.
            """
            ),
            "VC-VD-022",
        )

    except config_errors.InvalidOutDir as e:
        await publish_job_log(
            dedent(
                f"""
            Error: VC-VD-023. Invalid symbols for output directory.
            Timestamp: {TVP.ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: {TVP.common_line}

            Errors caused by:
                Output Dir: {PTO.output_dir}
                Issues: {str(e)}
            """
            ),
            "VC-VD-023",
        )
