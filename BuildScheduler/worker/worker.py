# worker.py - The individual worker process. Spawns as a detached process via nohup (linux only).
# This is main
# 
# Imports
import asyncio
import logging
import os
from textwrap import dedent
from dotenv import load_dotenv


load_dotenv("/home/vire/vire/.env")

from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.utils.state import worker_config

from BuildScheduler.shared.container_runtimes.errors import OutputDirNotFound
from BuildScheduler.shared.container_runtimes.base_runtime import ContainerRuntime
from BuildScheduler.shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from BuildScheduler.shared.logging.scheduler_logger import vire_logger

from BuildScheduler.worker.resolve_worker_state import update_job_state, fetch_job_status
from BuildScheduler.worker.cli_parser import load_parser

from BuildScheduler.worker.core.cleanup_container import remove_container
from BuildScheduler.worker.core.create_container_job import container_create
from BuildScheduler.shared.logging.pub_redis import publish_log_redis
from BuildScheduler.worker.schema.errors import CredentialError

runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()


def setup_logfile_location(job_uuid):
    """Sets up the logfile directory and locations."""
    worker_log_dir = os.path.join(worker_config.WORKER_LOGDIR, job_uuid)
    os.makedirs(worker_log_dir, exist_ok=True)
    return os.path.join(worker_log_dir, f"{job_uuid}.log")

async def stream_file(worker_context: WorkerContext):
    """
    Stream an archived file from the container.
    """

    try:
        status = fetch_job_status(job_uuid=worker_context.job_uuid, user_uuid=worker_context.user_uuid)
        if status == "cancelled":
            return
        output_path = os.path.join("/workspace", f"{worker_context.repo_name}", worker_context.OUTPUT_DIR)
        path_to_tar = os.path.join(worker_config.WORKER_OUTPUT_DIR, f"{worker_context.job_uuid}.tar")

        runtime.stream_file(
            job_uuid=worker_context.job_uuid,
            output_path=output_path,
            path_to_archive=path_to_tar
        )

    except OutputDirNotFound as e:
        status = fetch_job_status(job_uuid=worker_context.job_uuid, user_uuid=worker_context.user_uuid)
        if status == "cancelled":
            return
        vire_logger(
            "info", str(e),
            worker_context.OUTPUT_DIR, worker_context.job_uuid,
        )
        await publish_log_redis(dedent(
            f"""
            Error: {str(e)}

            Details:
                Dir given: '{worker_context.OUTPUT_DIR}' (In vire.toml)
                Job UUID: '{worker_context.job_uuid}'
                Clone link: {worker_context.remote}
                Commit SHA: '{worker_context.COMMIT_ID}'

            Suggested fixes:
                1. Check build configuration of the framework (vite.config.js if vite, etc.)
                     for the output directory and ensure it matches the one provided in vire.toml.
                2. Check the spelling of the output directories provided.
            """
        ), user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid)
    

# Helper
async def complete_final_tasks(worker_context: WorkerContext):
    """The function called for the finally block in main (try, except)."""
    # Main logic
    global runtime
    try:
        await stream_file(worker_context=worker_context)

    except Exception as e:
        vire_logger("critical", "Finally block function caught 'Exception'. %s", e)
        update_job_state(worker_context.job_uuid, "crashed", "running")
    try:
        await remove_container(worker_context=worker_context)
    except Exception as e:
        vire_logger("critical", "[worker entry_point] remove_container unable to remove the container. Details %s", e)
        raise e


# Main
async def main(worker_context: WorkerContext):
    job_uuid = worker_context.job_uuid
    try:
        assert job_uuid is not None, "Job UUID is None"
        await container_create(worker_context)
        await complete_final_tasks(worker_context=worker_context)

    except Exception as e:
        update_job_state(job_uuid, "running", "crashed")
        vire_logger("critical", "Vire faced an unexpected issue while trying to create a worker process. Details: %s", e)
        await publish_log_redis(dedent(
            """
            Error: VC-WK-001. Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        ), user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid) 


def init()-> WorkerContext:
    worker_context = load_parser()
    try:
        logfile_location = setup_logfile_location(worker_context.job_uuid)
        logging.basicConfig(filename=logfile_location, encoding="utf-8", level=logging.INFO)

        return worker_context

    except CredentialError as e:
        update_job_state(worker_context.job_uuid, "running", "crashed")
        vire_logger("exit", "[worker init()]-> CredentialError. The values provided have invalid None type.")
        asyncio.run(publish_log_redis(dedent(
            f"""
            Error: The data provided was invalid.

            Details:
                CredentialError. The values provided have invalid None type.

            Error:
                {e}
            """
        ), user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid))
        exit()

# Entry point
if __name__ == "__main__":
    worker_context = init()
    job_uuid = worker_context.job_uuid
    try:
        asyncio.run(main(worker_context= worker_context))

    except KeyError:
        update_job_state(job_uuid, "running", "crashed")
        vire_logger("critical", "The values provided don't match the expected JSON structure.")
        asyncio.run(publish_log_redis(dedent(
            """
            Error: The values provided don't match the expected JSON structure.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        ), user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid))

    except Exception as e:
        update_job_state(job_uuid, "running", "crashed")
        vire_logger("critical", "Vire faced an unexpected issue while trying to create a worker process. Details: %s", e)
        asyncio.run(publish_log_redis(dedent(
            """
            Error: Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        ), user_uuid= worker_context.user_uuid, job_uuid=worker_context.job_uuid))
