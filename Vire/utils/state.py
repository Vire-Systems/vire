import os
import logging
from pathlib import Path

# Available frameworks
available_frameworks_str = os.getenv("AVAILABLE_FRAMEWORKS")
assert available_frameworks_str is not None
available_frameworks: set[str] = set(available_frameworks_str.lower().split(","))

# Redis
redis_url = os.getenv("REDIS_URL")
assert redis_url is not None

# Logfile
logfile_dir = os.getenv("CORE_LOGDIR")
assert logfile_dir is not None, (
    f"'logfile_dir in {Path(__file__).resolve()} is {logfile_dir}."
)

os.makedirs(logfile_dir, exist_ok=True)
logfile: str = os.path.join(logfile_dir, "core.log")

# Logging
logging_values: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARN,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

log_level: str | None = os.getenv("LOG_LEVEL")
assert log_level is not None, f"log level in {Path(__file__).resolve()} is 'None'"

assert log_level is not None
log_value: int = logging_values[log_level.lower()]
