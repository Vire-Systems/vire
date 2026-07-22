from dataclasses import dataclass, field
from typing import Self

from shared.errors.base_error import VireBaseError
from shared.events.base_event import VireBaseEvent
from shared.utils.types import Severity

@dataclass(slots=True, kw_only=True)
class ErrorEvent(VireBaseEvent):
    """
    The Error Event of Vire.

    This event is a special subtype of standard events as this one carries an error field.
    It uses composition to carry an error field (The base of the said error has to be VireBaseError).

    Refer to BaseError's docstring for all details.
    """
    error: VireBaseError
    diag_code: str = field(init=False)
    summary: str = field(init=False)
    severity: Severity = field(init=False)
    event: str = "Error Event"

    propagate_state: bool = True
    write_log: bool = True

    def __post_init__(self: Self):
        self.diag_code = self.error.error_code
        self.summary = self.error.error_title
        self.severity = self.error.severity

    def get_extra_content(self) -> dict[str, tuple[str, ...] | None]:
        return {
            "possible_causes": self.error.possible_causes,
            "possible_fixes": self.error.possible_fixes,
            "notes": self.error.notes
        }
