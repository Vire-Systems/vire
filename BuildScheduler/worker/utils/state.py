import os
from pathlib import Path

# State
job_uuid = None
remote = None
user_uuid = None

install_req = False
COMMIT_ID: str | None = None

framework = None
package_manager = None
repo_name: str | None = None
OUTPUT_DIR: str | None = None

CONTAINER_EXPIRY = 300

# container runtime
container_runtime = os.getenv("CONTAINER_RUNTIME")

# Redis
redis_url = os.getenv("REDIS_URL")
assert redis_url is not None, f"Redis URL in {Path(__file__).resolve()} is {redis_url}."

# Files
logfile_dir = os.getenv("WORKER_LOGDIR")
db_file = os.getenv("DB_PATH")

assert db_file is not None, f"'db_file' in {Path(__file__).resolve()} is {db_file}."

assert logfile_dir is not None, f"'logfile_dir' in {Path(__file__).resolve()} is {logfile_dir}."