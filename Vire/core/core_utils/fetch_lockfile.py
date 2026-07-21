"""
This module (fetch_lockfile.py) is responsible for fetching the name of the lockfile present in the most recent commit.

Functions -
    1. fetch_lockfile_name 
"""

from Vire.objects.git_provider_adapter import PROVIDER_REGISTRY
from Vire.utils.async_requests import send_request
from shared.errors.validation_errors import GitProviderAPIError
from shared.shared_state import shared_config, lockfile_matrix
from shared.errors import vire_errors as errors 


async def fetch_lockfile_name(username: str, reponame: str, provider: str, commit_id: str, pm: str)-> str:
    """
    Fetches the lockfile in the provided commit of the provided repo.
    
    Returns the name of the lockfile.

    Behavior -
        1. Fetches the git trees using an adapter (check Vire/objects/git_provider_adapter).

    Raises -
        1. EmptyLockfile
        2. GitProviderAPIError (rare but possible if git_tree_node["path"] or git_tree_req.json()["trees"] does not exist.)
        3. NoLockfileError
    """
    try:
        adapter = PROVIDER_REGISTRY[provider]

        list_dir_url = adapter.return_list_tree(username, reponame, commit_id)
    
        gittree_content_req = await send_request(list_dir_url)
        trees = gittree_content_req.json()["tree"]
    
        for node in trees:
            path: str = node["path"]
            if path not in shared_config.VALID_LOCKFILES:
                continue
    
            if lockfile_matrix.get(path) != pm:
                continue
    
            if node["size"] == 0:
                raise errors.EmptyLockfileError(error_title= f"The lockfile ({path}) is empty.")
    
            if node["type"] != "blob":
                continue
                
            return path
    
        raise errors.NoLockfileError()
    except KeyError as key_error:
        raise GitProviderAPIError(error_title=f"{provider.capitalize()}'s Git tree API failed.") from key_error
    except errors.RepoFileFetchError as e:
        raise e
