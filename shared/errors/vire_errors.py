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

    error_title: str = "VC-VD-002. Unable to fetch vire.toml. The provided branch was invalid."
    error_code: str = "VC-VD-002"
    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"

    internal_log_body: str = "The provided branch was invalid."
    build_state: str = "failed_validation"

    possible_causes: tuple[str] | None = (
        "1. Branch was deleted right after triggering the Vire webhook.",
    )


# Unsupported PMs --
@dataclass(slots=True, kw_only=True)
class UnsupportedPackageManager(VireBaseError):
    """Raise for unsupported pms."""

    error_code: str = "VC-VD-015"
    error_title: str = "VC-VD-015. Unsupported package manager."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"

    internal_log_body: str = "The provided branch was invalid."
    build_state: str = "failed_validation"


# Empty lockfile --
@dataclass(slots=True, kw_only=True)
class EmptyLockfile(VireBaseError):
    """Raise when lockfile is empty."""

    error_code: str = "VC-VD-012"
    error_title: str = "Error: VC-VD-012. Empty lockfile."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"

    internal_log_body: str = "The logfile is empty for the job specified."
    build_state: str = "failed_validation"


# No lockfile --
@dataclass(slots=True, kw_only=True)
class NoLockfile(VireBaseError):
    """Raise when unable to find a lockfile."""

    error_code: str = "VC-VD-013"
    error_title: str = "Error: VC-VD-013. No lockfile."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "warn"

    internal_log_body: str = "Found no logfile for the job specified."
    build_state: str = "failed_validation"

    possible_fixes: tuple[str, ...] | None = (
        "1. Try setting 'dependencies=false' in vire.toml if installation of packages isn't needed for building the project.",
    )


# Unsupported Git providers --
@dataclass(slots=True, kw_only=True)
class UnsupportedGitProvider(VireBaseError):
    """Raise when the git provider isn't supported."""
    error_code: str = "VC-VD-005"
    error_title: str = "The git provider specified is not supported."

    severity: Literal[
        'info', 'warn', 'error', 'critical', 'exit'
    ] = "critical"

    internal_log_body: str = "The git provider provided for the job specified is not supported"
    build_state: str = "failed_validation"

    notes: tuple[str, ...] | None = (
        "1. Check docs for the details of this error.",
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

    internal_log_body: str = "The provider's raw CDN API failed for specified job uuid"
    build_state: str = "failed_validation"

    notes: tuple[str, ...] | None = (
        "Check documentation for detailed information regarding the error.",
    )
