"""
All the Vire specific events.
"""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from shared.utils.types import Severity
from shared.events.base_event import VireBaseEvent

@dataclass(slots=True, kw_only=True)
class GCReapEvent(VireBaseEvent):
    event: str = "Container Reaped"
    severity: Severity = "warn"
    diag_code: str = "VC-GC-001"

    write_log: bool = True
    propagate_state: bool = True

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