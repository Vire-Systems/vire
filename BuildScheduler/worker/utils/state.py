import os

from BuildScheduler.worker.schema.worker_dataclasses import WorkerConfig

worker_config = WorkerConfig(
    CONTAINER_EXPIRY=300,
    CONTAINER_RUNTIME=os.environ["CONTAINER_RUNTIME"],
    REDIS_URL=os.environ["REDIS_URL"],
    WORKER_OUTPUT_DIR=os.environ["WORKER_OUTPUT_DIR"],
    WORKER_LOGDIR=os.environ["WORKER_LOGDIR"],
    DB_FILE=os.environ["DB_PATH"],
)
