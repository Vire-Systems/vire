"""
This module is responsible for fetching and parsing the vire.toml.
Details provided by the user's requested repo, branch and commit SHA.

Functions -
    1. fetch_and_parse_toml
"""

from textwrap import dedent
from tomllib import TOMLDecodeError

from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml
from Vire.project_manifest.parse_toml import parse_toml
from Vire.project_manifest.errors import config_errors
from shared.errors import vire_errors as errors 
from Vire.utils.publish_job_log import publish_job_log

from Vire.objects.dataclass_objects.validation_models import ValidatorContext, ParsedTOMLObject

async def fetch_and_parse_toml(VC: ValidatorContext, ts: str)-> ParsedTOMLObject | None:
    """
    This function fetches and parses vire.toml.
    
    Args -
        TO - ValidatorContext, Toml object with toml data.

    returns -
        ParsedTOMLObject
    """

    try:
        vire_toml_str = await fetch_vire_toml(
            provider=VC.provider, remote_user=VC.remote_user, remote_reponame=VC.remote_reponame, branch=VC.branch
        )
        verified_toml: ParsedTOMLObject = await parse_toml(vire_toml_str)

        return verified_toml

    except TOMLDecodeError as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-003. Unable to validate vire.toml.

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: Root Directory of {VC.branch}, {VC.remote_reponame}
                Issue: {str(e)}

            Suggested fixes:
                1. Use official docs' vire.toml as reference.
            """), "VC-VD-003")

    except errors.InvalidBranchError:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-002. Unable to fetch vire.toml.

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: Root Directory of {VC.branch}, {VC.remote_reponame}

            Possible reasons it can happen:
                1. Branch '{VC.branch}' was deleted right after triggering the Vire webhook.
            """), "VC-VD-002")
    
    except config_errors.InvalidVireToml as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-003. Unable to validate vire.toml.

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Fetched from: Root Directory of {VC.branch}, {VC.remote_reponame}
                Issue: {str(e)}

            Suggested fixes:
                1. Use official docs' vire.toml as reference.
            """), "VC-VD-003")
    
    except errors.RepoFileFetchError as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-004. Unable to fetch files from the repository '{VC.remote_reponame}.'

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Issue: {e}
            """), "VC-VD-004")

    except errors.UnsupportedGitProviderError as e:
        await publish_job_log(dedent(
            f"""
            Error: VC-VD-005. The git provider '{VC.provider}' is not supported.

            Details:
                Job UUID: {VC.job_uuid}
                Commit SHA: {VC.commit_id}
                Branch Name: {VC.branch}
                Issue: {e}
            """
        ), "VC-VD-005")
