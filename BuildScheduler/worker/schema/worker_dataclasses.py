"""
This module (worker_dataclasses) provides a dataclass called 'FrameworkAdapter'.

Consists -
1. FrameworkAdapter
2. WorkerContext
3. WorkerConfig
"""

from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class FrameworkAdapter:
    """Dataclass for framework data."""

    image: str
    install_command: dict[str, str]
    build_command: dict[str, str]


@dataclass(frozen=True, slots=True)
class WorkerContext:
    """Context required for worker"""

    job_uuid: str
    user_uuid: str
    remote: str
    repo_name: str
    framework: str
    package_manager: str
    install_req: bool
    OUTPUT_DIR: str
    COMMIT_ID: str


@dataclass(slots=True)
class WorkerConfig:
    CONTAINER_EXPIRY: int
    CONTAINER_RUNTIME: str
    REDIS_URL: str
    WORKER_OUTPUT_DIR: str
    WORKER_LOGDIR: str
    DB_FILE: str

    def __post_init__(self):
        for field in fields(self):
            if getattr(self, field.name) is None:
                raise ValueError(f"{field.name} cannot be 'None'.")
