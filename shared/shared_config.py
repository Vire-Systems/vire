from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SharedConfig:
    CORE_ID: str
    CANCELLABLE_BUILD_STATES: set[str]
    VALID_LOCKFILES: tuple[str, ...]
    VALID_PMS: tuple[str, ...]
    CONTAINER_RUNTIME: str
    CONTAINER_METADATA: MappingProxyType[str, str]
