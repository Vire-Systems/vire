from dataclasses import dataclass
from typing import Literal

@dataclass(slots= True, kw_only=True)
class VireBaseError(Exception):
    """
    Base class for all Vire-specific exceptions.

    Every exception raised by Vire should inherit from this class. It provides
    a standardized structure for propagating error information throughout the
    system while allowing centralized handling for logging, database updates,
    and user-facing responses.

    Instances of this class are intended to carry metadata only. They do not
    perform logging or persistence themselves; that responsibility belongs to
    the centralized exception handler.

    Attributes:
    ----------
    error_code:
        Stable identifier used by the logging system and databases.

    error_title:
        Short, human-readable title describing the error. Intended for the user.

    severity:
        Logging severity associated with the exception.

    Optional Attributes:
    ---------
    These are sent to the User Report.

    possible_causes
    possible_fixes
    notes - suggestions to the user
        
        
    """

    error_title: str
    error_code: str

    severity: Literal[
        "info",
        "warn",
        "error",
        "critical",
        "exit",
    ]

    # Optionals
    possible_causes: tuple[str, ...] | None = None
    possible_fixes : tuple[str, ...] | None = None
    notes: tuple[str, ...] | None = None

    def __post_init__(self):
        super().__init__(self.error_title)

