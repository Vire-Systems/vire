from dataclasses import dataclass, field
from datetime import datetime, UTC
from shared.utils.types import Severity


@dataclass(slots=True)
class VireBaseEvent:
    """
    Base event contract for all events emitted within Vire.

    Every event, including ErrorEvent, must inherit from this class.
    The event handler expects an instance of this contract to process
    logging, state propagation, and external communication.

    Attributes
    ----------
    event : str
        Name of the event being emitted.

    job_uuid : str
        UUID of the associated build job.

    user_uuid : str
        UUID of the user associated with the build job.

    diag_code : str
        Diagnostic reference code associated with the event.

    severity : Severity
        Severity level used for logging and external propagation.

    summary : str
        One-line summary describing what occurred. Used for internal
        logs and user-facing reports.

    write_log : bool
        Whether this event should be written to the internal logger.

    propagate_state : bool
        Whether this event should be propagated to external systems.
        This may include updating PostgreSQL, publishing through Redis,
        or notifying supported integrations.

    timestamp : datetime
        UTC timestamp representing when the event was created.
    """

    event: str
    job_uuid: str
    user_uuid: str
    diag_code: str
    severity: Severity
    summary: str

    # These are mostly for API enforcement so logging / propagation actually happens depending upon the event.
    write_log: bool
    propagate_state: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_extra_content(self) -> dict[str, tuple[str, ...] | None]:
        return {}

    def get_log_extras(self) -> dict[str, str]:
        return {}
