"""
Dataclasses or regular classes used by the container runtime adapter.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    managed_by: str
    expires_at: str | None


# Note: use 'None' when using RuntimeMetadata for fetching expired containers.
# It should ignore expires_at since it fetches that from the container runtime itself.
