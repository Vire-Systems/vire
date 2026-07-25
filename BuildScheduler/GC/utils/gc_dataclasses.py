from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GCConfig:
    LOGFILE_DIR: str
    REDIS_URL: str
    DB_PATH: str
    LOG_LEVEL: int
    CONTAINER_REMOVAL_DELAY: int
