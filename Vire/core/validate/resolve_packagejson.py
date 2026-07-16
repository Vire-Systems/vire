"""
This module handles the orchestration of the functions which fetch and validate the package.json file from a user repository.

Functions -
    1. fetch_and_validate_pkgjson
"""

from textwrap import dedent

from Vire.utils.publish_job_log import publish_job_log
from Vire.core.core_utils.fetch_buildreq import fetch_package_json
from Vire.project_manifest.validator import validate_package_json

from BuildScheduler.shared.errors import vire_errors as errors 
from Vire.project_manifest.errors import config_errors
from Vire.objects.dataclass_objects.validation_models import ValidatorContext, PkgJSONValidationParams


async def fetch_and_validate_pkgjson(
    VC: ValidatorContext,
    PJVP: PkgJSONValidationParams
)-> bool | None:
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

    except config_errors.InvalidPackageJson as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-031. Invalid 'package.json'.
            Timestamp: {PJVP.ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}

            Errors caused by:
                Issue: {e}

            The scripts in 'package.json' cannot be accepted by Vire. 
            """), "VC-VD-031")

    except errors.InvalidBranchError:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-032. Branch does not exist.
            Timestamp: {PJVP.ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}

            Suggested fixes:
                1. In the case of branch deletion, retry.

            If branch exists and you see this error, create an issue on GitHub regarding this. (Internal parsing error)
            """), "VC-VD-032")

    except errors.RepoFileFetchError as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-033. File fetch from remote failed.
            Timestamp: {PJVP.ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}

            Error details - {e}

            Suggested Fixes:
                1. Check {VC.provider.capitalize()}'s status
                2. Could be caused by the package.json file being malformed.
                3. Outdated Commit SHA because something was pushed right after the build started (1-3s delay between pushes.)
            """), "VC-VD-033")

    except errors.UnsupportedGitProvider as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-034. Unsupported git provider {VC.provider.capitalize()}.
            Timestamp: {PJVP.ts}

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Issue: {e}
            """), "VC-VD-034")
