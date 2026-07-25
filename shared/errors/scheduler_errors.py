"""
This module handles all the custom db exceptions used in crud.py.

Contains -
    1. NoJobStateError
"""

from dataclasses import dataclass

from shared.errors.base_error import VireBaseError
from shared.utils.types import Severity


@dataclass(slots=True, kw_only=True)
class NoJobStateError(VireBaseError):
    """Raised when Job state doesn't exist in the db."""

    error_title: str = "Job State for the job does not exist."
    error_code: str = "VC-IN-NO_JOB_STATE"
    severity: Severity = "critical"

    notes: tuple[str, ...] | None = (
        "This is an internal error. Please open a report if you see this.",
    )
