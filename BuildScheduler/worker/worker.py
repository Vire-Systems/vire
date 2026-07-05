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

from resolve_worker_state import fetch_job_status, update_job_state
from cli_parser import load_parser
from core.cleanup_container import remove_container
from core.create_container_job import container_create
from core.stream_redis_log import publish_log_redis
from docker.errors import NotFound
from schema.errors import CredentialError
from utils import state
from utils.vire_logger import cfn_log

client = state.client

def setup_logfile_location(job_uuid):
    """Sets up the logfile directory and locations."""
    assert state.logfile_dir is not None
    worker_log_dir = os.path.join(state.logfile_dir, job_uuid)
    os.makedirs(worker_log_dir, exist_ok=True)
    return os.path.join(worker_log_dir, f"{job_uuid}.log")


# Helper
def complete_final_tasks():
    """The function called for the finally block in main (try, except)."""
    #Helper
    def stream_file():
        try:
            assert state.job_uuid is not None
            worker_output_dir = os.getenv("WORKER_OUTPUT_DIR")
            assert worker_output_dir is not None
            assert state.user_uuid is not None

            stream, stat = client.api.get_archive(state.job_uuid, output_path)

            if fetch_job_status(job_uuid=state.job_uuid, user_uuid=state.user_uuid) == "cancelled":
                return
            path_to_tar = os.path.join(worker_output_dir, f"{state.job_uuid}.tar")
            with open(path_to_tar, "wb") as tar_file:
                for chunk in stream:
                    tar_file.write(chunk)
            update_job_state(state.job_uuid, "finished", "running")

        except NotFound:
            assert state.user_uuid is not None
            assert state.job_uuid is not None

            status = fetch_job_status(job_uuid=state.job_uuid, user_uuid=state.user_uuid)
            cfn_log("info", status)
            if status == "cancelled":
                return
            cfn_log(
                "info", "The output_path (%s) given for job '%s' doesn't exist inside the container.",
                output_dir, state.job_uuid,
            )
            publish_log_redis(dedent(
                f"""
                Error: The output directory given ({output_dir}) does not exist in the container.

                Details:
                    Dir given: '{output_dir}' (In vire.toml)
                    Job UUID: '{state.job_uuid}'
                    Clone link: {state.remote}
                    Commit SHA: '{state.COMMIT_ID}'

                Suggested fixes:
                    1. Check build configuration of the framework (vite.config.js if vite, etc.)
                         for the output directory and ensure it matches the one provided in vire.toml.
                    2. Check the spelling of the output directories provided.
                """
            ))

    # Main logic
    try:
        assert state.OUTPUT_DIR is not None, "Output directory is None"
        assert state.job_uuid is not None
        output_dir = state.OUTPUT_DIR
        output_path = os.path.join("/workspace", f"{state.repo_name}", output_dir)
        stream_file()
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
