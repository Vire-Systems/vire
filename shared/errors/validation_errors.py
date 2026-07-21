"""
This module (config_errors) provides custom errors for config related errors.

Errors -
1. InvalidPackageJsonError
2. InvalidVireTomlError
3. PackageManagerException
4. InvalidOutDirError 
"""
from dataclasses import dataclass

from shared.errors.base_error import VireBaseError
from shared.utils.types import Severity

@dataclass(slots=True, kw_only=True)
class InvalidPackageJsonError(VireBaseError):
    """Exception for Invalid package.json."""
    error_code: str = "VC-VD-INVALID_PACKAGE_JSON"
    severity: Severity = "warn"
    error_title: str = "The package.json found contains invalid scripts (postinstall, ...)"

    notes: tuple[str, ...] | None = (
        "The scripts in 'package.json' cannot be accepted by Vire.",
    )


@dataclass(slots=True, kw_only=True)
class InvalidTomlSyntaxError(VireBaseError):
    """Exception for when vire.toml fails to decode (aka TOMLDecodeError)"""
    error_title: str = "The TOML syntax is invalid."
    error_code: str = "VC-VD-INVALID_TOML_SYNTAX"
    severity: Severity = "warn"

    possible_fixes: tuple[str, ...] | None = (
        "Use the template from the official Vire documentation as a reference.",
    )
    
@dataclass(slots=True, kw_only=True)
class InvalidVireTomlError(VireBaseError):
    """Exception for invalid vire.toml."""
    error_title: str = "The schema of vire.toml is invalid."
    error_code: str = "VC-VD-INVALID_VIRE_TOML"
    severity: Severity = "warn"

    possible_fixes: tuple[str, ...] | None = (
        "Use the template from the official Vire documentation as a reference.",
    )


@dataclass(slots=True, kw_only=True)
class PackageManagerException(VireBaseError):
    """Exception for package manager exception."""
    error_title: str = "The package manager provided is not supported by Vire yet."
    error_code: str = "VC-VD-UNSUPPORTED_PM"
    severity: Severity = "warn"

@dataclass(slots=True, kw_only=True)
class GitProviderAPIError(VireBaseError):
    """Exception to raise when sure that Git provider's API failed."""
    error_code: str = "VC-IN-GIT_PROVIDER_API_FAILED"
    severity: Severity = "critical"

    notes: tuple[str, ...] | None = (
        "If you see this, it means that the Git Provider's API failed.",
        "Please create a report on this. Thank you."
    )
    

@dataclass(slots=True, kw_only=True)
class InvalidOutDirError(VireBaseError):
    """Exception for invalid/malicious output dir."""
    error_code:str = "VC-VD-INVALID_OUTPUT_DIRECTORY"
    severity: Severity = "warn"

    possible_fixes: tuple[str, ...] | None = (
        "Remove all characters other than alphanumerical characters, '-' (hyphens) and '_' (underscores).",
    )

@dataclass(slots=True, kw_only=True)
class UnsupportedFrameworkError(VireBaseError):
    """Exception for unsupported/invalid frameworks"""
    error_code: str = "VC-VD-UNSUPPORTED_FRAMEWORK"
    error_title: str = "The given framework is not supported by Vire yet."
    severity: Severity = "info"

    notes: tuple[str, ...] | None = (
        "Try uploading the files in HTML.",
        "Create a GitHub issue to add a new framework."
    )
