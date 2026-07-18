import logging
import os
from BuildScheduler.GC.utils.gc_dataclasses import GCConfig

os.makedirs(os.environ["GC_LOGDIR"], exist_ok=True)

logging_values: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn" : logging.WARN,
    "error": logging.ERROR,
    "critical" : logging.CRITICAL
}

log_level: str = os.environ["LOG_LEVEL"]

gc_config = GCConfig(
    LOGFILE_DIR = os.environ["GC_LOGDIR"],
    REDIS_URL = os.environ["REDIS_URL"],
    DB_PATH = os.environ["DB_PATH"],
    LOG_LEVEL = logging.INFO,
    CONTAINER_REMOVAL_DELAY=int(os.environ["CONTAINER_REMOVAL_DELAY"])
)
