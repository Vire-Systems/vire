from dataclasses import dataclass
from typing import Literal
from shared.errors.base_error import VireBaseError

# Note: The comments on top of each class is for separating the classes at a glance

# Invalid branch --
@dataclass(slots=True, kw_only=True)
class InvalidBranchError(VireBaseError):
    """
    Raise for Invalid / Unprovided branches
    """

    error_title: str = "Unable to fetch vire.toml. The provided branch was invalid."
    error_code: str = "VC-VD-002"
    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"

    possible_causes: tuple[str, ...] | None = (
        "Branch was deleted right after triggering the Vire webhook.",
    )


# Unsupported PMs --
@dataclass(slots=True, kw_only=True)
class UnsupportedPMError(VireBaseError):
    """Raise for unsupported package managers"""

    error_code: str = "VC-VD-015"
    error_title: str = "Unsupported package manager. The PM provided is unsupported."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"


# Empty lockfile --
@dataclass(slots=True, kw_only=True)
class EmptyLockfileError(VireBaseError):
    """Raise when lockfile is empty."""

    error_code: str = "VC-VD-012"
    error_title: str = "Empty lockfile in the provided branch."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"


# No lockfile --
@dataclass(slots=True, kw_only=True)
class NoLockfileError(VireBaseError):
    """Raise when unable to find a lockfile."""

    error_code: str = "VC-VD-013"
    error_title: str = "No lockfile found in the branch. Details below"

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"


    possible_fixes: tuple[str, ...] | None = (
        "Try setting 'dependencies=false' in vire.toml if installation of packages isn't needed for building the project.",
        "Try running `npm in`"
    )


# Unsupported Git providers --
@dataclass(slots=True, kw_only=True)
class UnsupportedGitProviderError(VireBaseError):
    """Raise when the git provider isn't supported."""
    error_code: str = "VC-VD-005"
    error_title: str = "The git provider specified is not supported."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "critical"

    notes: tuple[str, ...] | None = (
        "Check documentation for the details of this error.",
    )


# Repo file fetch error --
@dataclass(slots=True, kw_only=True)
class RepoFileFetchError(VireBaseError):
    """Raise when raw file fetch from client provided URL fails."""
    error_code: str = "VC-VD-014"
    error_title: str = "Error: VC-VD-014. Git provider API failed."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "critical"

    notes: tuple[str, ...] | None = (
        "Check documentation for detailed information regarding the error.",
    )
