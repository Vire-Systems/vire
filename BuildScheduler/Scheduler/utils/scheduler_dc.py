"""
This module (scheduler_dc 'scheduler dataclasses') is responsible for providing dataclasses to the scheduler.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """
    The immutable config dataclass used by Scheduler.
    """
    REDIS_URL: str
    SQLITE_DB_PATH: str
    DB_URL: str
    PYTHON_BIN_PATH: str
    WORKER_PACKAGE_LOCATION: str
    MAX_BUILDS_NUMBER: int
    CONTAINER_REMOVAL_DELAY: int


@dataclass(frozen=True, slots=True)
class WorkerCreationParams:
    """
    Parameters for '`create_worker_process`' function. Returned with data by CRUD's fetch_worker_data function.
    """

    job_uuid: str
    user_uuid: str
    remote_link: str
    commit_id: str
    repo_name: str
    framework: str
    pm: str
    install_req: bool
    output_dir: str
