# worker.py - The individual worker process. Spawns as a detached process via nohup (linux only).
# This is main
#
# Imports
import asyncio
import logging
import os
from dotenv import load_dotenv


_ = load_dotenv("/home/vire/vire/.env")

from BuildScheduler.worker.cli_parser import load_parser
from BuildScheduler.worker.core.cleanup_container import remove_container
from BuildScheduler.worker.core.create_container_job import container_create
from BuildScheduler.worker.resolve_worker_state import fetch_job_status, update_job_state
from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.utils.state import worker_config

from shared.container_runtimes.base_runtime import ContainerRuntime
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.errors.container_runtime_errors import OutputDirNotFound
from shared.errors.worker_errors import CredentialError
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.events.error_event import ErrorEvent

runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()


def setup_logfile_location(job_uuid: str):
    """Sets up the logfile directory and locations."""
    worker_log_dir = os.path.join(worker_config.WORKER_LOGDIR, job_uuid)
    os.makedirs(worker_log_dir, exist_ok=True)
    return os.path.join(worker_log_dir, f"{job_uuid}.log")


async def stream_file(WC: WorkerContext):
    """
    Stream an archived file from the container.
    """
    try:
        status = fetch_job_status(job_uuid=WC.job_uuid, user_uuid=WC.user_uuid)
        if status == "cancelled":
            return

        output_path = os.path.join("/workspace", f"{WC.repo_name}", WC.OUTPUT_DIR)
        path_to_tar = os.path.join(worker_config.WORKER_OUTPUT_DIR, f"{WC.job_uuid}.tar")

        runtime.stream_file(job_uuid=WC.job_uuid, output_path=output_path, path_to_archive=path_to_tar)

    except OutputDirNotFound as e:
        status = fetch_job_status(job_uuid=WC.job_uuid, user_uuid=WC.user_uuid)
        if status == "cancelled":
            return
        await dispatch_event(
            event=ErrorEvent(job_uuid=WC.job_uuid, user_uuid=WC.user_uuid, error=e),
            job_details={
                "Dir given": f"'{WC.OUTPUT_DIR}' (In vire.toml)",
                "Clone link": WC.remote,
                "Commit SHA": WC.COMMIT_ID,
            },
        )


# Helper
async def complete_final_tasks(worker_context: WorkerContext):
    """The function called for the finally block in main (try, except)."""
    # Main logic
    global runtime
    try:
        await stream_file(WC=worker_context)
        await remove_container(worker_context=worker_context)

    except Exception:
        raise


# Main
async def main(worker_context: WorkerContext):
    job_uuid = worker_context.job_uuid
    try:
        assert job_uuid is not None, "Job UUID is None"
        await container_create(worker_context)
        await complete_final_tasks(worker_context=worker_context)

    except Exception as e:
        await dispatch_event(event=LogEvent(
            user_uuid=worker_context.user_uuid,
            job_uuid=worker_context.job_uuid,
            diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
            severity="critical",
            summary="Unexpected issue while trying to create/end a worker process.",
            source="worker",
            exception_name=type(e).__name__,
            internal_log=None, propagate_state=True
        ))
        update_job_state(job_uuid, prev_status="running", status="crashed")

def init() -> WorkerContext:
    worker_context = load_parser()
    try:
        logfile_location = setup_logfile_location(worker_context.job_uuid)
        logging.basicConfig(filename=logfile_location, encoding="utf-8", level=logging.INFO)

        return worker_context

    except CredentialError:
        update_job_state(worker_context.job_uuid, "running", "crashed")
        raise


# Entry point
if __name__ == "__main__":
    worker_context = init()
    job_uuid = worker_context.job_uuid
    asyncio.run(main(worker_context=worker_context))
