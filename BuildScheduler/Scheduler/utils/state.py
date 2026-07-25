import os
import asyncio
from BuildScheduler.Scheduler.utils.scheduler_dc import SchedulerConfig


scheduler_config = SchedulerConfig(
    CONTAINER_REMOVAL_DELAY=int(os.environ["CONTAINER_REMOVAL_DELAY"]),
    REDIS_URL=os.environ["REDIS_URL"],
    SQLITE_DB_PATH=os.environ["DB_PATH"],
    DB_URL=os.environ["DB_URL"],
    PYTHON_BIN_PATH=os.environ["PYTHON_BIN_PATH"],
    WORKER_PACKAGE_LOCATION=os.environ["WORKER_PACKAGE_LOCATION"],
    MAX_BUILDS_NUMBER=int(os.environ["MAX_BUILDS_NUMBER"]),
)

# State
removal_tasks: set[asyncio.Task[None]] = set()
