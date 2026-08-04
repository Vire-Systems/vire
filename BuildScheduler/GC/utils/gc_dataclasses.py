"""
Provides GC with the GCConfig dataclass.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GCConfig:
    """
    The immutable configuration used by the Vire GC for its config options.
    """

    LOGFILE_DIR: str
    REDIS_URL: str
    DB_PATH: str
    LOG_LEVEL: int
    CONTAINER_REMOVAL_DELAY: int
