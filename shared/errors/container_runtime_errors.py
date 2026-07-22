"""
The Vire exceptions raised to abstract the Container rutime adapter's specific errors.
"""

from dataclasses import dataclass

from shared.errors.base_error import VireBaseError
from shared.utils.types import Severity


@dataclass(slots=True, kw_only=True)
class ContainerCreationFail(VireBaseError):
    """Exception for Container creation failure."""
    error_title: str
    error_code: str = "SANDBOX_CREATION_FAIL"
    severity: Severity = "critical"

    notes: tuple[str, ...] | None = (
        "Internal Error.",
        "Create a bug report / Issue on GitHub if you see this."
    )

@dataclass(slots=True, kw_only=True)
class OutputDirNotFound(VireBaseError):
    """Raised when the given output dir does not exist in the container."""
    error_title: str = "Output Directory given in vire.toml does not exist in the sandbox."
    error_code: str = "VC-WK-OUTPUT_DIR_NOT_FOUND"
    severity: Severity = "warn"

    possible_fixes: tuple[str, ...] | None = (
        "Ensure the output directory configured in your framework (eg vite.config.js) matches the output directory in vire.toml.",
        "Check the spelling of the output directories provided."
    )

@dataclass(slots=True, kw_only=True)
class ContainerAdapterAPIError(VireBaseError):
    """General catch all error. Raise instead of raising an Exception."""
    error_title: str
    error_code: str = "VC-IN-SANDBOX_RUNTIME_FAIL"
    severity: Severity = "critical"

@dataclass(slots=True, kw_only=True)
class ContainerNotFound(VireBaseError):
    """Raised when the container removal is already in progress"""
    error_title: str = "Container not found."
    error_code: str = "VC-IN-SANDBOX_NOT_FOUND"

    severity: Severity = "info"
