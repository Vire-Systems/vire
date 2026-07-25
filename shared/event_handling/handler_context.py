"""
The context class for handling errors in Vire.
"""

from dataclasses import dataclass
from datetime import datetime

from shared.utils.types import Severity


@dataclass(slots=True, frozen=True)
class EventHandlerContext:
    event: str
    timestamp: datetime
    diag_code: str
    severity: Severity
    summary: str

    job_uuid: str
    user_uuid: str

    possible_causes: tuple[str, ...] | None = None
    possible_fixes: tuple[str, ...] | None = None
    notes: tuple[str, ...] | None = None
    job_details: dict[str, str] | None = None
