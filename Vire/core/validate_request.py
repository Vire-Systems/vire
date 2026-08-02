"""
This module (validate_request) is responsible for providing an abstracted interface for validation.

Handles fetching, validation, etc.
"""

import traceback
from datetime import datetime

from Vire.core.core_utils.fetch_buildreq import fetch_vire_toml
from Vire.core.core_utils.fetch_con import fetch_data_concurrently
from Vire.core.validate.parse_vire_toml import parse_vire_toml
from Vire.core.validate.validate_lockfile import validate_lockfile
from Vire.core.validate.validate_vire_toml import validate_vire_toml
from Vire.core.validate.resolve_packagejson import validate_pkgjson

from Vire.objects.validation_models import (
    ValidatorContext,
    ParsedTOMLObject,
    LockfileValidationParams,
    TOMLValidationParams,
)


# Validate
async def validate_details(VC: ValidatorContext) -> ParsedTOMLObject | None:
    """
    The abstracted function for validating build data (vire.toml, package.json, lockfile verification) provided by the user.

    Handles:
    --------

    1. fetching vire.toml, package.json from the git provider.
    2. parsing the provided vire.toml and checking its schema.
    3. Validating the package.json (see validate_package_json docstring) and vire.toml.
    4. Creating a worker when it passes all checks.

    Args:
    -----

    - VC: ValidatorContext, abbreviation. Dataclass for data needed for the validator.
    """

    # Helper for datetime string
    def ts():
        """Returns the current datetime in the format '%d-%m-%Y, %H:%M:%S'"""
        return datetime.now().strftime("%d-%m-%Y, %H:%M:%S")

    try:
        common_line = f"the branch {VC.branch} from {VC.remote_user}'s repository named {VC.remote_reponame} from {VC.provider.capitalize()}"

        # Main logic -
        # Fetch and parse toml
        provider_data = await fetch_data_concurrently(VC=VC)

        if not provider_data:
            return

        toml_data: ParsedTOMLObject | None = await parse_vire_toml(VC=VC, vire_toml_str=provider_data.vire_toml_str)
        if toml_data is None:
            return

        # Lockfile validation
        lockfile_params = LockfileValidationParams(
            install_req=toml_data.install_req,
            commit_id=VC.commit_id,
            package_manager=toml_data.package_manager,
            provider=VC.provider,
        )

        lockfile_name = await validate_lockfile(
            LVP=lockfile_params,
            VC=VC,
            lockfile_names=provider_data.lockfile_names
        )

        if lockfile_name is None:
            return

        # Validate toml
        validate_data_obj = TOMLValidationParams(
            lockfile_name=lockfile_name, common_line=common_line, ts=ts()
        )

        if await validate_vire_toml(TVP=validate_data_obj, VC=VC, PTO=toml_data) is None:
            return

        # fetch and validate package.json
        is_valid = await validate_pkgjson(
            VC=VC, 
            package_json_str=provider_data.package_json_str
        )

        if not is_valid:
            return

        return toml_data
    except Exception:
        traceback.print_exc()
