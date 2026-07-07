"""
This module (fetch_toml) fetches the toml file from a remote.

Functions -
    1. fetch_vire_toml
    2. fetch_package_json
"""

from Vire.objects.git_provider_adapter import PROVIDER_REGISTRY
from Vire.errors import errors
from Vire.utils.async_requests import send_request


# TOML fetch
async def fetch_vire_toml(
        provider: str,
        remote_user: str, remote_reponame: str,
        branch : str
    )-> str:
    """
    Fetches vire.toml from 'master' on the provided provider's File content fetching APIs.
    
    Args -
        1. provider - The name of the git provider (ex: 'github', 'gitlab', etc)
        2. remote_user - The username of the build requester. (ex: Vire-Systems in "https://github.com/Vire-Systems/...")
        3. remote_reponame - The repository name (ex: vire in "https://github.com/Vire-Systems/vire/...")
        4. path - The path to the req file.
        5. branch - Latest branch which was pushed.
    
    Raises -
        InvalidBranchError, RepoFileFetchError, UnsupportedGitProvider
    Catches -
        Broad 'Exception'
    """
    try:
        adapter = PROVIDER_REGISTRY[provider]
        if not branch:
            raise errors.InvalidBranchError

        toml_raw_url = adapter.get_raw_url(remote_user, remote_reponame, branch, ".vire/vire.toml")
        body = await send_request(toml_raw_url)
        toml_b:bytes = body.content
        toml_str = toml_b.decode(encoding="utf-8")
        return toml_str

    except KeyError as KE:
        raise errors.UnsupportedGitProvider(f"The Git provider '{provider}' is not supported yet.") from KE
    except errors.InvalidBranchError:
        raise
    except errors.RepoFileFetchError:
        raise
    except Exception:
        raise errors.RepoFileFetchError("While trying to fetch vire.toml, Vire encountered unexpected errors (Internal Error).")


# package.json fetch
async def fetch_package_json(
        provider: str,
        remote_user: str, remote_reponame: str,
        branch: str
    )-> str:
    """
    Fetches package.json from the provided provider's File content fetching APIs.
    
    Args -

        1. provider - The name of the git provider (ex: 'github', 'gitlab', etc)
        2. remote_user - The username of the build requester. (ex: Vire-Systems in "https://github.com/Vire-Systems/...")
        3. remote_reponame - The repository name (ex: vire in "https://github.com/Vire-Systems/vire/...")
        4. path - The path to the req file.
        5. branch - Latest branch which was pushed.

    Raises -
        InvalidBranchError, RepoFileFetchError, UnsupportedGitProvider
    """
    try:
        adapter = PROVIDER_REGISTRY[provider]
        if not branch:
            raise errors.InvalidBranchError(f"Provided branch ('{branch}')  is Invalid.")
    
        packagejson_raw_url = adapter.get_raw_url(user=remote_user, repo_name=remote_reponame, branch=branch, path_name="package.json")
        body = await send_request(packagejson_raw_url)
        packagejson_bytes = body.content
        packagejson_str = packagejson_bytes.decode(encoding="utf-8")
    
        return packagejson_str
    except KeyError as KE:
        raise errors.UnsupportedGitProvider(f"The Git provider '{provider}' is not supported yet.") from KE
        
    except errors.InvalidBranchError as e:
        raise e
        
    except errors.RepoFileFetchError as e:
        raise e
        
    except Exception:
        raise errors.RepoFileFetchError("While trying to fetch package.json, Vire encountered unexpected errors (Internal Error).")