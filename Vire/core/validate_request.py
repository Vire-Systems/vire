"""
This module (validate_request) is responsible for providing an abstracted interface for validation.

Handles fetching, validation, etc.
"""

import traceback
from datetime import datetime

from Vire.core.validate.fetch_parse_toml import fetch_and_parse_toml
from Vire.core.validate.validate_lockfile import fetch_and_validate_lockfile
from Vire.core.validate.validate_vire_toml import validate_vire_toml
from Vire.core.validate.resolve_packagejson import fetch_and_validate_pkgjson

from Vire.objects.validation_models import(
    ValidatorContext,
    ParsedTOMLObject,
    LockfileValidationParams,
    TOMLValidationParams,
)

# Validate
async def validate_details(VC: ValidatorContext)-> ParsedTOMLObject | None:
    """
    The abstracted function for validating build data (vire.toml, package.json, lockfile verification) provided by the user.

    Handles all intermediary processes like:
    
        1. fetching vire.toml, package.json from the git provider.
        2. parsing the provided vire.toml and checking its schema.
        3. Validating the package.json (see validate_package_json docstring) and vire.toml.
        4. Creating a worker when it passes all checks.

    Args:
        VC - ValidatorContext, abbreviation. Dataclass for data needed for the validator.
    
    Errors raised by the base functions used (caught by underlying functions):
    
        1. InvalidBranchError (fetch_vire_toml)
        2. InvalidVireTomlError (parse_toml)
        3. EmptyLockfile, KeyErrror, NoLockfileError (fetch_lockfile)
        4. InvalidPackageJsonError, PackageManagerException, InvalidOutDirError (validate_toml)
        5. InvalidBranchError (fetch_package_json)
        6. InvalidPackageJsonError (validate_package_json)
        7. UnsupportedGitProviderError (fetch_vire_toml, fetch_package_json, fetch_lockfile_name)
    """
    
    # Helper for datetime string
    def ts():
        """Returns the current datetime in the format '%d-%m-%Y, %H:%M:%S'"""
        return datetime.now().strftime('%d-%m-%Y, %H:%M:%S')
    try:
        common_line = f"the branch {VC.branch} from {VC.remote_user}'s repository named {VC.remote_reponame} from {VC.provider.capitalize()}"

    # Main logic -
    # Fetch and parse toml
        toml_data: ParsedTOMLObject | None = await fetch_and_parse_toml(VC=VC)
        if not toml_data:
            return

    # Lockfile validation
        lockfile_params = LockfileValidationParams(
            install_req=toml_data.install_req,
            commit_id=VC.commit_id,
            package_manager=toml_data.package_manager,
            provider=VC.provider
        )
        
        lockfile_name = await fetch_and_validate_lockfile(
            LVP=lockfile_params,
            VC=VC
        )
        if not lockfile_name:
            return

    # Validate toml
        validate_data_obj = TOMLValidationParams(
            lockfile_name=lockfile_name,
            common_line=common_line,
            ts=ts()
        )
        
        if not await validate_vire_toml(TVP=validate_data_obj, VC=VC, PTO=toml_data):
            return

    # fetch and validate package.json
        if not await fetch_and_validate_pkgjson(VC=VC):
            return

        return toml_data
    except Exception:
        traceback.print_exc()
