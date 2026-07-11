
import os
from textwrap import dedent

import docker
import time

from docker.client import DockerClient
from docker.errors import NotFound, APIError

from core.stream_redis_log import publish_log_redis
from resolve_worker_state import fetch_job_status, update_job_state
from schema.errors import ContainerCreationFail, InstallReqMismatch
from utils.vire_logger import cfn_log

from utils import state

from schema.base_runtime import ContainerRuntime



class DockerRuntime(ContainerRuntime):

# Client
    def get_client(self)-> DockerClient:
        """Return the docker client."""
        return docker.from_env()

# Container creation
    def create(self, job_uuid: str):
        """
        Run a docker container synchronously.
    
        Args:
            job_uuid - Job UUID of the container job. Also used as container name.
    
        Raises 'worker.schema.errors.ContainerCreationFail' if container fails to spin up.
        """
    
        from core.create_container_job import setup_creation
        try:
            client = self.get_client()
            expires_at = int(time.time() + state.CONTAINER_EXPIRY)
            if (state.repo_name is None) or (state.framework is None) or (state.package_manager is None):
                return
            image, cmd_body = setup_creation(state.repo_name, state.framework, state.package_manager)
    
            if not image or not cmd_body:
                raise ContainerCreationFail(f"{'Image' if not image else 'cmd'} Cannot be none.")
            cmd = ["sh", "-c", cmd_body]
            client.containers.run(
                name=job_uuid,
                image=image,
                command=cmd,
                mem_limit="400m",
                cpu_quota=50000,
                cpu_period=100000,
                detach=True,
                labels={"managed_by": "build_scheduler", "expires_at": str(expires_at)},
            )
        except InstallReqMismatch as e:
            raise ContainerCreationFail(str(e))
        except Exception as e:
            cfn_log("critical", "[sync_docker_run] Job '%s' was unsuccessful. Details: %s", job_uuid, e)
            raise ContainerCreationFail(f"Container spin up unsucessful. Details: {e}") from e

# Extract artifacts
    def stream_file(self):
        try:
            assert state.job_uuid is not None
            worker_output_dir = os.getenv("WORKER_OUTPUT_DIR")
            assert worker_output_dir is not None
            assert state.user_uuid is not None
            assert state.OUTPUT_DIR is not None
    
            output_path = os.path.join("/workspace", f"{state.repo_name}", state.OUTPUT_DIR)

            client = self.get_client()
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
                state.OUTPUT_DIR, state.job_uuid,
            )
            publish_log_redis(dedent(
                f"""
                Error: The output directory given ({state.OUTPUT_DIR}) does not exist in the container.
    
                Details:
                    Dir given: '{state.OUTPUT_DIR}' (In vire.toml)
                    Job UUID: '{state.job_uuid}'
                    Clone link: {state.remote}
                    Commit SHA: '{state.COMMIT_ID}'
    
                Suggested fixes:
                    1. Check build configuration of the framework (vite.config.js if vite, etc.)
                         for the output directory and ensure it matches the one provided in vire.toml.
                    2. Check the spelling of the output directories provided.
                """
            ))

# Remove container
    def remove(self, job_uuid: str):
        """Name (UUID4 used for naming) based container remover"""
        try:
            client = self.get_client()
            container_obj = client.containers.get(job_uuid)
        except NotFound:
            container_obj = None
            pass
        try:
            if container_obj:
                container_obj.wait()
                container_obj.remove(force=True)

        except APIError as e:
            if "is already in progress" in str(e).lower():
                cfn_log("info", "[remove_container] Conflict: GC's termination in progress")
            else:
                cfn_log("critical", "[remove_container]-> docker.errors.APIError: Removal of container '%s' was unsuccessful. Details: %s",
                        job_uuid, e
                )
        except Exception as e:
            cfn_log("critical", "[remove_container] Removal of container '%s' was unsuccessful. Details: %s", job_uuid, e)
            raise e

# Fetch log lines from container
    def get_container_log(self, job_uuid):
        client = self.get_client()
        container_obj = client.containers.get(job_uuid)

        for line in container_obj.logs(stream=True, follow=True, stdout=True, stderr=True, timestamps=True):
            yield line