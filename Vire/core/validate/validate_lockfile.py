"""
This module handles orchestrating the fetch and validation process for the lockfile from data provided when requesting a build.

Functions -
    1. fetch_and_validate_lockfile
"""

from textwrap import dedent

from BuildScheduler.shared.shared_state import package_managers_list

from Vire.errors import errors
from Vire.objects.dataclass_objects.validation_models import LockfileValidationParams, ValidatorContext
from Vire.project_manifest.errors import config_errors
from Vire.core.core_utils.fetch_lockfile import fetch_lockfile_name
from Vire.utils.publish_job_log import publish_job_log

async def fetch_and_validate_lockfile(
    LVP: LockfileValidationParams,
    VC: ValidatorContext,
    ts: str,
    common_line: str
)-> str | None:
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
                raise config_errors.PackageManagerException(f"The package manager provided ({LVP.package_manager}) isn't supported by Vire yet.")

            lockfile_name = await fetch_lockfile_name(
            username=VC.remote_user,
            reponame=VC.remote_reponame,
            provider=VC.provider,
            commit_id=LVP.commit_id,
            pm=LVP.package_manager
        )
        else:
            return

        return lockfile_name

    # Exception handling
    except config_errors.PackageManagerException as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-015. Unsupported package manager.
            Timestamp: {ts}

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                PM provided: {LVP.package_manager}

            Error details: {e}
            """
        ), "VC-VD-015")

    except errors.EmptyLockfile as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-012. Empty lockfile.
            Timestamp: {ts}

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: {common_line}
                Lockfile path: '{e}'
            """), "VC-VD-012")

    except KeyError:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-011. Check docs for details.
            Timestamp: {ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Tried to fetch from: {common_line}

            Brief overview:
                {VC.provider.capitalize()}'s git tree api returned malformed JSON. 
            """), "VC-VD-011")

    except errors.NoLockfile:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-013. No lockfile.
            Timestamp: {ts}

            Job Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: {common_line}

            Potential fixes:
                Try setting 'dependencies=false' in vire.toml if installation of packages isn't needed for building the project.
            """,), "VC-VD-013")

    except errors.RepoFileFetchError as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-014. Check docs for error definition.
            Timestamp: {ts}

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Tried to fetch from: {common_line}
                Issue: {e}
            """
        ), "VC-VD-014")
