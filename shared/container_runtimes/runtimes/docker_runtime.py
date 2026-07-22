"""
Docker runtime adapter.

This module provides the `DockerRuntime` implementation.

1. Provides Vire's implementation of abstract container runtime interface using the official `docker` SDK.
2. Responsible for translating runtime operations into Docker API calls.
3. Converts Docker errors into Vire specific errors.
"""

import asyncio
import time
from typing import AsyncGenerator, Generator

import docker
from docker.client import DockerClient
from docker.errors import APIError, NotFound
from docker.models.containers import Container

from shared.container_runtimes.base_runtime import ContainerRuntime
from shared.errors.container_runtime_errors import (
    ContainerAdapterAPIError,
    ContainerCreationFail,
    ContainerNotFound,
    OutputDirNotFound,
)
from shared.container_runtimes.runtime_dc import RuntimeMetadata


class DockerRuntime(ContainerRuntime):
    def __init__(self):
        self.client = docker.from_env()

    # Client ----
    def get_client(self) -> DockerClient:
        """Return the docker client."""
        return self.client


    # Container creation ---
    def create(self, job_uuid: str, image: str, cmd: list[str], metadata: RuntimeMetadata) -> None:
        """
        Run a docker container synchronously.
        Intended to be used by the worker package.

        metadata would look like
        {
            managed_by : vire
            expires_at : some str(int)
        }
        """
        try:
            client = self.get_client()
            if metadata.expires_at is None:
                raise ValueError("expires_at is required for container creation.")

            labels = {"managed_by": metadata.managed_by, "expires_at": str(metadata.expires_at)}
            client.containers.run(
                name=job_uuid,
                image=image,
                command=cmd,
                mem_limit="400m",
                cpu_quota=50000,
                cpu_period=100000,
                detach=True,
                labels=labels,
            )

        except ValueError:
            raise
        except APIError as e:
            raise ContainerCreationFail(error_title="Container creation failed. Docker raised APIError.") from e
        except Exception as e:
            raise ContainerCreationFail(error_title=f"Container spin up unsuccessful. Details: {e}") from e


    # Remove container ----
    def remove(self, job_uuid: str) -> None:
        """Name (UUID4 used for naming) based container remover"""
        try:
            client = self.get_client()
            container_obj = client.containers.get(job_uuid)
            container_obj.wait()
            container_obj.remove(force=True)

        except NotFound:
            raise ContainerNotFound

        except ContainerNotFound:
            raise
        except APIError as e:
            if e.status_code == 409:
                return
            raise ContainerAdapterAPIError(error_title="Docker API Error.") from e

        except Exception as e:
            raise ContainerAdapterAPIError(error_title="Unexpected error occured while removing the container") from e


    # Extract artifacts ----
    def stream_file(self, job_uuid: str, output_path: str, path_to_archive: str) -> None:
        """Stream the file content inside the docker container as an archive (tar file)."""

        try:
            client = self.get_client()
            stream, _stat = client.api.get_archive(job_uuid, output_path)

            with open(path_to_archive, "wb") as tar_file:
                for chunk in stream:
                    tar_file.write(chunk)

        except NotFound as e:
            raise OutputDirNotFound(
                error_title="The output directory given in vire.toml does not exist in the container."
            ) from e


    # Fetch log lines from container ----
    def get_container_log(self, job_uuid) -> Generator[bytes, None, None]:
        """Yield a line of stdout from the container."""
        try:
            client = self.get_client()
            container_obj = client.containers.get(job_uuid)

            for line in container_obj.logs(stream=True, follow=True, stdout=True, stderr=True, timestamps=True):
                yield line

        except Exception as e:
            raise ContainerAdapterAPIError(
                error_title="Unable to fetch container logs from container. Unexpected error."
            ) from e


    async def list_managed_containers(
        self, metadata: RuntimeMetadata, count: bool, all: bool = False
    ) -> int | AsyncGenerator[str, None]:
        """
        If count is False,
        Yields container names (aka job_uuid) of containers managed by vire from docker.

        If count is true,
        Returns the number of containers.

        #  NOTE:
            Do NOT expose Exception messages to users. It is STRICTLY INTERNAL.

        Raises:
        -------
        ContainerAPIError
        """
        try:
            client = self.get_client()
            filter_labels: dict[str, str | list[str] | bool] = {
                "label": [
                    f"managed_by={metadata.managed_by}",
                ]
            }
            raw_container_list: list[Container] = await asyncio.to_thread(
                client.containers.list, all=all, filters=filter_labels
            )

            if count:
                return len(raw_container_list)

            async def return_async_generator() -> AsyncGenerator[str, None]:
                for container in raw_container_list:
                    if not container.name:
                        continue
                    yield container.name

            return return_async_generator()
        except Exception as e:
            raise ContainerAdapterAPIError(error_title="unable to get Scheduler managed containers.") from e


    async def list_expired_containers(self, metadata: RuntimeMetadata) -> AsyncGenerator[str, None]:
        """
        Yield the job_uuids (aka names) of expired containers.

        # NOTE:
            Do NOT expose Exception messages to users. It is STRICTLY INTERNAL.

        Raises:
        -------
        ContainerAdapterAPIError
        """
        try:
            now_time: int = int(time.time())
            client = self.get_client()
            filter_labels: dict[str, str | list[str] | bool] = {
                "label": [
                    f"managed_by={metadata.managed_by}",
                ]
            }

            raw_container_list: list[Container] = await asyncio.to_thread(
                client.containers.list, all=True, filters=filter_labels
            )

            for container_obj in raw_container_list:
                if int(container_obj.labels.get("expires_at", now_time)) <= now_time - 15:
                    if container_obj.name is None:
                        continue
                    yield container_obj.name

        except Exception as e:
            raise ContainerAdapterAPIError(error_title="unable to get containers which are overdue.") from e
