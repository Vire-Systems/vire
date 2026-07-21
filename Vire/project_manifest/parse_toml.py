"""
This module (parse_toml) is the master script that handles toml validation.

Functions-
1. parse_toml
"""

import tomllib
from Vire.project_manifest.schema_check import check_toml_schema
from shared.errors.validation_errors import InvalidVireTomlError
from Vire.objects.validation_models import ParsedTOMLObject

async def parse_toml(toml_string: str)-> ParsedTOMLObject:
    """
    Parses vire.toml from toml string.
    
    Args -
        toml_string - string returned from reading the repo's vire.toml.

    Returns:
        ParsedTOMLObject

    Raises:
        'InvalidVireTomlError' if 'check_toml_schema' raises InvalidVireTomlError
    
    Catches:
        InvalidVireTomlError and reraises it.
    """
    try:
        toml_dict = tomllib.loads(toml_string)
        return await check_toml_schema(toml_dict)
    except InvalidVireTomlError as e:
        raise e
