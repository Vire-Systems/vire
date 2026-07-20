"""
All the Vire specific events.
"""

from dataclasses import dataclass

from shared.utils.types import Severity
from shared.events.base_event import VireBaseEvent

@dataclass(slots=True, kw_only=True)
class GCReapEvent(VireBaseEvent):
    event: str = "ContainerReaped"
    severity: Severity = "warn"
    diag_code: str = "VC-GC-CONTAINER_REAPED"

    write_log: bool = True
    propagate_state: bool = True


@dataclass(slots=True, kw_only=True)
class ContainerTimeoutEvent(VireBaseEvent):
    event: str = "ContainerTimedOut"
    severity: Severity = "info"
    diag_code: str = "VC-SC-CONTAINER_TIMED_OUT"

    write_log: bool = True
    propagate_state: bool = True


@dataclass(slots=True, kw_only=True)
class InfoEvent(VireBaseEvent):
    """
    This event is for 
    """
    event: str = "InfoEvent"
    severity: Severity = "info"

    write_log: bool = True
    propagate_state: bool = True

    extra_details: dict[str, tuple[str, ...] | None] | None = None
    extra_log_details: dict[str, str] | None = None

    def get_extra_content(self) -> dict[str, tuple[str, ...] | None]:
        return self.extra_details if self.extra_details else {}

    def get_log_extras(self) -> dict[str, str]:
        return self.extra_log_details if self.extra_log_details else {}


@dataclass(slots=True, kw_only=True)
class LogEvent(VireBaseEvent):
    
    """
    This event is a special child instance of BaseEvent.
    Use this to send log events to the handler.

    By default job_uuid, user uuid are "SYSTEM".

    By default write_log is True and propagate_state is False.

    Internal log extras:
    ---
    exception_name, source, internal_log
    """
    job_uuid: str = "SYSTEM"
    user_uuid: str = "SYSTEM"
    event: str = "Log Event"
    
    source: str
    exception_name: str
    internal_log: str | None

    write_log:bool = True
    propagate_state: bool = False
    

    def get_log_extras(self) -> dict[str, str]:
        log_extras = {
            "exception_name": self.exception_name,
            "source":self.source,
        }
        log_extras.update({"reason":self.internal_log} if self.internal_log else {})
        return log_extras