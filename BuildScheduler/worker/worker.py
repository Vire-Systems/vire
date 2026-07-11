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

from BuildScheduler.worker.schema.base_runtime import ContainerRuntime
from resolve_worker_state import update_job_state
from cli_parser import load_parser

from core.cleanup_container import remove_container
from core.create_container_job import container_create
from core.stream_redis_log import publish_log_redis
from schema.errors import CredentialError

from utils import state
from utils.vire_logger import cfn_log
from utils.container_runtimes.runtime_registry import RUNTIME_REGISTRY

assert state.container_runtime
runtime: ContainerRuntime = RUNTIME_REGISTRY[state.container_runtime]()


def setup_logfile_location(job_uuid):
    """Sets up the logfile directory and locations."""
    assert state.logfile_dir is not None
    worker_log_dir = os.path.join(state.logfile_dir, job_uuid)
    os.makedirs(worker_log_dir, exist_ok=True)
    return os.path.join(worker_log_dir, f"{job_uuid}.log")


# Helper
def complete_final_tasks():
    """The function called for the finally block in main (try, except)."""
    # Main logic
    global runtime
    try:
        assert state.OUTPUT_DIR is not None, "Output directory is None"
        assert state.job_uuid is not None

        runtime.stream_file()

    except Exception as e:
        assert state.job_uuid is not None
        cfn_log("critical", "Finally block function caught 'Exception'. %s", e)
        update_job_state(state.job_uuid, "crashed", "running")
    try:
        job_uuid = state.job_uuid
        if job_uuid:
            remove_container(job_uuid=job_uuid)
    except Exception as e:
        cfn_log("critical", "[worker entry_point] remove_container unable to remove the container. Details %s", e)
        raise e


# Main
async def main():
    try:
        assert state.job_uuid is not None, "Job UUID is None"
        await container_create(state.job_uuid)
        complete_final_tasks()

    except Exception as e:
        assert state.job_uuid is not None, "Job_UUID is None"
        update_job_state(state.job_uuid, "running", "crashed")
        cfn_log("critical", "Vire faced an unexpected issue while trying to create a worker process. Details: %s", e)
        publish_log_redis(dedent(
            """
            Error: VC-WK-001. Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        )) 


def init():
    try:
        load_parser()
        logfile_location = setup_logfile_location(state.job_uuid)
        logging.basicConfig(filename=logfile_location, encoding="utf-8", level=logging.INFO)

    except CredentialError as e:
        assert state.job_uuid is not None, "Job UUID is None"

        update_job_state(state.job_uuid, "running", "crashed")
        cfn_log("critical", "[worker init()]-> CredentialError. The values provided have invalid None type.")
        publish_log_redis(dedent(
            f"""
            Error: The data provided was invalid.

            Details:
                CredentialError. The values provided have invalid None type.

            Error:
                {e}
            """
        ))

# Entry point
if __name__ == "__main__":
    try:
        init()
        asyncio.run(main())
    except KeyError:
        assert state.job_uuid is not None, "Job UUID is None"
        update_job_state(state.job_uuid, "running", "crashed")
        cfn_log("critical", "The values provided don't match the expected JSON structure.")
        publish_log_redis(dedent(
            """
            Error: The values provided don't match the expected JSON structure.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        ))
    except AssertionError as e:
        if state.job_uuid:
            update_job_state(state.job_uuid, "running", "crashed")
            cfn_log("critical", "[worker entry_point]-> AssertionError while trying to create a worker process. Details: %s", str(e))
            publish_log_redis(dedent(
                f"""
                Error: Vire faced an unexpected issue while trying to create a worker process.
    
                If you see this error, Please create an issue on github with a screenshot. This is an internal error.

                Issue: {e}
                """
            ))
    except Exception as e:
        assert state.job_uuid is not None, "Job_UUID is None"
        update_job_state(state.job_uuid, "running", "crashed")
        cfn_log("critical", "Vire faced an unexpected issue while trying to create a worker process. Details: %s", e)
        publish_log_redis(dedent(
            """
            Error: Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.
            """
        ))
