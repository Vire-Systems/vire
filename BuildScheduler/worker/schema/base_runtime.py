"""The master class inherited by all Container runtime classes"""

class ContainerRuntime:

    def get_client(self):
        raise NotImplementedError

    def create(self, job_uuid: str):
        """Create a container. Synchronous function"""
        raise NotImplementedError

    def remove(self, job_uuid: str):
        raise NotImplementedError

    def stream_file(self):
        raise NotImplementedError

    def get_container_log(self, job_uuid):
        raise NotImplementedError
