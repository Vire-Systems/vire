"""
This module (scheduler_dc 'scheduler dataclasses') is responsible for providing dataclasses to the scheduler.
"""

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    REDIS_URL : str
    SQLITE_DB_PATH : str
    DB_URL: str 
    PYTHON_BIN_PATH: str
    WORKER_PACKAGE_LOCATION: str
    MAX_BUILDS_NUMBER: int
    CONTAINER_REMOVAL_DELAY: int

@dataclass(frozen=True, slots=True)
class WorkerCreationParams():
    """
    Params for create_worker_process function. Returned with data by CRUD's fetch_worker_data function.

    Attributes -
        job_uuid, user_uuid, remote, repo_name, framework, pm, install_req, output_dir, commit_id
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