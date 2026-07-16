"""The master class inherited by all Container runtime classes"""

from typing import AsyncGenerator, Generator

from BuildScheduler.shared.container_runtimes.runtime_dc import RuntimeMetadata


class ContainerRuntime:

    def get_client(self):
        raise NotImplementedError

    def create(
        self,
        job_uuid: str,
        image: str,
        cmd: list[str],
        metadata: RuntimeMetadata
    )-> None:
        """
        Run a container synchronously.
        Intended to be used by the worker package.
    
        Args
        ----
        job_uuid - Job UUID of the container job. Also used as container name.
        image - Name of the image to use.
        cmd - The command to run
        metadata - Build metadata to add to creation.
    
        Raises
        ------
        ContainerCreationFail when catching
            1. Broad excepts
            2. Container creation specific errors.
        """
        raise NotImplementedError

    def remove(self, job_uuid: str)-> None:
        """
        Remove a container using it's name (job_uuid).

        Args
        ----
        job_uuid - Name for the container to avoid collisions.

        Raises
        ------
        ContainerAdapterAPIError
        ContainerNotFound
        """
        raise NotImplementedError

    def stream_file(
        self,
        job_uuid: str,
        output_path: str,
        path_to_archive: str
    )-> None:
        """
        Stream the finished artifacts as an archive.

        Args
        ----
        job_uuid - Name of the container
        user_uuid - UUID of the user who requested the build
        output_path - The path to artifacts inside the container
        path_to_archive - Host filesystem location to stream the file to (Should not expose host filesystem)

        Raises
        ------
        OutputDirNotFound(str):
            - If the container runtime cannot find the provided output_path in the container. 
            - Returns the cause of failure in the error body.
        """
        raise NotImplementedError

    def get_container_log(self, job_uuid: str)-> Generator[bytes]:
        """
        Stream logs from the container.

        Args
        ----
        job_uuid: Name of the container

        Raises
        ------
        ContainerAdapterAPIError:
            - General catch (exception)
        """
        raise NotImplementedError

    async def list_managed_containers(self, metadata: RuntimeMetadata, count: bool, all: bool =False)-> int | AsyncGenerator[str, None]:
        """
        Yields the names (aka job_uuid) of containers managed by Vire.

        Returns:
        --------
        if count = False; AsyncGenerator of container names that are managed by vire
        if count = True; Returns the number of said containers 

        Raises:
        ContainerAdapterAPIError
        ------
        """
        if False:
            yield

        raise NotImplementedError

    async def list_expired_containers(self, metadata: RuntimeMetadata)-> AsyncGenerator[str, None]:
        """
        Yields the name (aka job_uuid) of containers that have expired.
        Intended to be used by the GC or somewhere where expired containers' names are needed.

        Raises:
        ------

        ContainerAdapterAPIError
        """
        if False:
            yield
        raise NotImplementedError
