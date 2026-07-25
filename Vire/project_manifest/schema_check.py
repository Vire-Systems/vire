"""
This module (schema_chech.py) checks the vire.toml schema.

Functions -

1. check_toml_schema
"""

from typing import Any

from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from Vire.objects.validation_models import ParsedTOMLObject
from shared.errors.validation_errors import InvalidVireTomlError


async def check_toml_schema(toml_dict: dict) -> ParsedTOMLObject:
    """
    Validates the schema of the toml file. Also returns whether package install is required.

    Args:
        toml_dict: The dictionary format of toml using tomllib.load.

    Returns:
        ParsedTOMLObject

    Raises "BuildScheduler.Scheduler.project_manifest.errors.config_errors.InvalidVireTomlError" if toml is malformed.
    Raise returns a string with all missing toml_dict keys.
    Catches broad Exceptions.
    """
    try:
        output_str = ""
        details: dict[str, str] | None = toml_dict.get("details")
        if not details:
            raise InvalidVireTomlError(error_title="[details] table not found.")

        framework = details.get("framework")
        package_manager = details.get("package_manager")

        project: dict[str, str] | None = toml_dict.get("project")
        if not project:
            raise InvalidVireTomlError(error_title="[project] table not found")

        output_dir: str = project.get("output_dir")
        framework_version: str = project.get("framework_version")
        dependencies_req: bool = project.get("dependencies")

        if not framework:
            output_str += "'framework' cannot be empty. "
        if not package_manager:
            output_str += "'package_manager' cannot be empty. "
        if not output_dir:
            output_str += "output_dir cannot be empty. "
        if not framework_version:
            output_str += "framework_version cannot be empty. "
        if not dependencies_req:
            output_str += "'dependencies' cannot be empty."

        if output_str:
            raise InvalidVireTomlError(error_title=output_str)

        return ParsedTOMLObject(
            framework=framework,
            package_manager=package_manager,
            framework_version=framework_version,
            output_dir=output_dir,
            install_req=dependencies_req,
        )
    except InvalidVireTomlError as e:
        raise e
    except Exception as e:
        await dispatch_event(
            event=LogEvent(
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                summary="Unable to parse vire.toml of the user (raised Exception)",
                source="validation",
                exception_name=type(e).__name__,
                internal_log=None,
            )
        )
        raise InvalidVireTomlError(
            error_title="Internal error while parsing vire.toml.",
            error_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
            severity="critical",
        )
