"""
All the Vire specific events.
"""

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

e = GCReapEvent(
    job_uuid="test", user_uuid="sparrow", summary="summary"
)

print(e)