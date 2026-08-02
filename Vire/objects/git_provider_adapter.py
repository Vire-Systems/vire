"""
This module (remote_adapter) is responsible for providing remote (github,gitlab, etc) details.

"""

from typing import override


class GitProviderAdapter:
    """
    Master class for all provider specific classes.

    Methods-
        1. get_raw_url
        2. return_clone_link

    """

    def get_raw_url(
        self, user: str, repo_name: str, branch: str, path_name: str
    ) -> str:
        """Returns raw url for the path specified."""
        raise NotImplementedError

    def return_clone_link(self, user: str, repo_name: str) -> str:
        """Returns a repository clone link."""
        raise NotImplementedError

    def return_default_branch(self) -> str:
        """Returns default fallback branch, ie; 'main'."""
        return "main"

    def return_list_tree(self, user: str, reponame: str, commit_id: str) -> str:
        """
        Returns the git tree contents (dir list) of the given commit id.

        1. user - username under git provider.
        2. reponame - Name of the repo.
        3. commit_id - SHA of the commit.
        """
        raise NotImplementedError


# Adapters


class GithubAdapter(GitProviderAdapter):
    """
    Adapter for Github. Inherits 'GitProviderAdapter'.
    """

    @override
    def get_raw_url(
        self, user: str, repo_name: str, branch: str, path_name: str
    ) -> str:
        return (
            f"https://raw.githubusercontent.com/{user}/{repo_name}/{branch}/{path_name}"
        )

    @override
    def return_clone_link(self, user: str, repo_name: str):
        return f"https://github.com/{user}/{repo_name}.git"

    @override
    def return_list_tree(self, user: str, reponame: str, commit_id: str):
        return f"https://api.github.com/repos/{user}/{reponame}/git/trees/{commit_id}"

PROVIDER_REGISTRY: dict[str, type[GitProviderAdapter]] = {
    "github": GithubAdapter,
}
