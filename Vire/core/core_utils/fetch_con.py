

import asyncio

from Vire.core.core_utils.fetch_buildreq import fetch_package_json, fetch_vire_toml
from Vire.core.core_utils.fetch_lockfile import fetch_lockfile_name
from Vire.objects.validation_models import IOFetchedContent, ValidatorContext
from shared.errors.validation_errors import GitProviderAPIError, InvalidIODataError

from shared.errors.vire_errors import (
    EmptyLockfileError, InvalidBranchError, NoLockfileError, RepoFileFetchError, UnsupportedGitProviderError
)
from shared.event_handling.handler import dispatch_event
from shared.events.error_event import ErrorEvent


async def fetch_data_concurrently(VC: ValidatorContext)-> IOFetchedContent | None:
    try:
        tasks: list[asyncio.Task[str | list[str]]] = [
    
            asyncio.create_task(fetch_vire_toml(
                provider=VC.provider,
                remote_user=VC.remote_user,
                remote_reponame=VC.remote_reponame,
                branch=VC.branch,
            )),
    
            asyncio.create_task(fetch_package_json(
                provider=VC.provider,
                remote_user=VC.remote_user,
                remote_reponame=VC.remote_reponame,
                branch=VC.branch,
            )),
    
            asyncio.create_task(fetch_lockfile_name(
                username=VC.remote_user,
                reponame=VC.remote_reponame,
                provider=VC.provider,
                commit_id=VC.commit_id,
            )),
    
        ]
    
        vire_toml_str, package_json_str, lockfile_names = await asyncio.gather(*tasks, return_exceptions=True)

    # These are guaranteed to be true. The type checker is being an annoying brat rn.
        if not isinstance(vire_toml_str, str):
            raise InvalidIODataError()

        if not isinstance(package_json_str, str):
            raise InvalidIODataError()

        if not isinstance(lockfile_names, list):
            raise InvalidIODataError()
    # End of pointless checking

        return IOFetchedContent(
            vire_toml_str = vire_toml_str,
            package_json_str = package_json_str,
            lockfile_names = lockfile_names
        )

    # Error handling
    except (
        InvalidBranchError, RepoFileFetchError, UnsupportedGitProviderError,
        EmptyLockfileError, NoLockfileError, GitProviderAPIError, InvalidIODataError
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
