"""
All dataclasses used in the validator.
"""

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ValidatorContext:
    """
    A dataclass for vire.toml data as an object.

    Attributes -
        job_uuid, user_uuid, provider, remote_user, remote_reponame, branch, commit_id
    """
    job_uuid: str
    user_uuid: str
    provider: str
    remote_user: str
    remote_reponame: str
    branch: str
    commit_id: str


# TOML
@dataclass(frozen=True, slots=True)
class ParsedTOMLObject:
    """
    A dataclass with parsed toml data.

    Attributes - 
        framework, package_manager, framework_version, output_dir, install_req
    """
    framework: str
    package_manager: str
    framework_version: str
    output_dir: str
    install_req: bool

@dataclass(frozen=True, slots=True)
class TOMLValidationParams:
    """
    A dataclass for the params of the function 'validate_vire_toml'.

    Attributes - 
        lockfile_name, common_line, ts
    """
    lockfile_name: str | None
    common_line: str
    ts: str


# Lockfile
@dataclass(frozen=True, slots=True)
class LockfileValidationParams:
    """
    A dataclass for the params of the function 'fetch_and_validate_lockfile'.

    Attributes - 
        install_req, commit_id, package_manager, provider
    """
    install_req : bool
    commit_id: str
    package_manager: str
    provider: str


# package.json
@dataclass(frozen=True, slots=True)
class PkgJSONValidationParams:
    """
    A dataclass for the params of the function 'fetch_and_validate_pkgjson'.

    Attributes - 
        lockfile_name, common_line, ts
    """
    lockfile_name: str | None
    common_line: str
    ts: str