"""
This module (validator) Validates the package.json.

Functions-

1. validate_pakage_json (async)
2. validate_toml (async)
"""

import json
import re

from shared.shared_state import lockfile_matrix
from shared.errors import validation_errors
from Vire.utils.state import available_frameworks

# frameworks vite, astro, vue, react, sveltekit, nextjs, nuxtjs, 11ty
# pms: npm, pnpm, yarn, bun


# package.json
async def validate_package_json(package_json_str: str) -> bool:
    """
    Validates package.json and raises errors mentioned below. Is a Helper called by 'validate_toml'.

    Args:
        package.json - str

    Behavior:
        Returns False if "{"preinstall", "postinstall", "install", "prepare", "prepublish"}" is present in pacakge.json[scripts].

    Raises:
        validation_errors.InvalidPackageJsonError
    """
    try:
        package_json = json.loads(package_json_str)
        blocked_keys = {
            "start",
            "preinstall",
            "postinstall",
            "install",
            "prepare",
            "prepublish",
        }
        scripts = package_json.get("scripts", {})
        found_keys = [key for key in blocked_keys if key in scripts]

        if found_keys:
            raise validation_errors.InvalidPackageJsonError(
                error_title="The following keys cannot be present in package.json. The invalid keys: {list(key for key in found_keys)}"
            )
        return True

    except validation_errors.InvalidPackageJsonError:
        raise
    except Exception as e:
        raise validation_errors.InvalidPackageJsonError(
            error_title="Encountered unexpected errors while attempting to parse package.json. Internal Error",
            error_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
            severity="critical",
        ) from e


# TOML
async def validate_toml(
    lockfile_name: str | None, package_manager: str, output_dir: str, framework: str
) -> None:
    """
    Validates the vire.toml file.

    Raises -

    'PackageManagerException' -
        1. if the given package_manager (arg) is invalid (unsupported).
        2. if lockfile given does not match the lockfile of the provided package manager.

    'InvalidOutDirError' -
        1. If output_dir provided fails regex check (r[a-zA-Z0-9_]+).

    'UnsupportedFrameworkError'
        1. If framework is not in FRAMEWORK_REGISTRY's keys.
    """
    if framework.lower() not in available_frameworks:
        raise validation_errors.UnsupportedFrameworkError(
            error_title="The framework provided ({framework}) is either unsupported or invalid."
        )

    if lockfile_name:
        if lockfile_matrix.get(lockfile_name) != package_manager:
            raise validation_errors.PackageManagerException(
                error_title=f"The lockfile ('{lockfile_name}') fetched by Vire does not match the Lockfile associated with the package manager ('{package_manager}') provided in your vire.toml."
            )

    allowed = re.fullmatch(r"[a-zA-Z0-9_-]+", output_dir)
    if not allowed:
        raise validation_errors.InvalidOutDirError(
            error_title=f"The output directory ({output_dir}) is not allowed. Only alphanumeric, hyphens and underscore characters are allowed."
        )
