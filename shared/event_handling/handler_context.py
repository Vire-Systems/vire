"""
The context class for handling errors in Vire.
"""

from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class ErrorHandlerContext:
    error_code: str
    error_title: str
    job_uuid: str
    possible_causes:  tuple[str, ...] | None
    possible_fixes:  tuple[str, ...] | None
    notes:  tuple[str, ...] | None
    job_details: dict[str, str] | None = None
