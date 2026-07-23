"""
Integration/Unit tests for shared/container_runtimes/runtimes/docker_runtime.py

Covers:
  - create (arguments mapped correctly, APIError translation)
  - remove (wait & remove called, NotFound -> ContainerNotFound translation)
  - stream_file (api.get_archive called, NotFound translation)
  - get_container_log (logs generator consumed, exception translation)
  - list_managed_containers (count=True vs count=False)
  - list_expired_containers (checks expires_at label against current time)

External dependencies patched:
  - docker.from_env (to avoid needing a live Docker daemon)
"""

from unittest.mock import MagicMock, patch
import pytest

PATCH_DOCKER_FROM_ENV = "docker.from_env"


class TestDockerRuntime:

    @pytest.fixture
    def mock_docker(self):
        with patch(PATCH_DOCKER_FROM_ENV) as mock_from_env:
            mock_client = MagicMock()
            mock_from_env.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def runtime(self, mock_docker):
        from shared.container_runtimes.runtimes.docker_runtime import DockerRuntime
        return DockerRuntime()

    @pytest.fixture
    def metadata(self):
        from shared.container_runtimes.runtime_dc import RuntimeMetadata
        return RuntimeMetadata(managed_by="test-scheduler", expires_at="2000000000")


    # ── create ────────────────────────────────────────────────────────────────

    def test_create_maps_args_to_containers_run(self, runtime, mock_docker, metadata, job_uuid):
        runtime.create(
            job_uuid=job_uuid, 
            image="test-image", 
            cmd=["echo", "hello"], 
            metadata=metadata
        )
        
        mock_docker.containers.run.assert_called_once()
        kwargs = mock_docker.containers.run.call_args[1]
        
        assert kwargs["name"] == job_uuid
        assert kwargs["image"] == "test-image"
        assert kwargs["command"] == ["echo", "hello"]
        assert kwargs["detach"] is True
        assert kwargs["labels"]["managed_by"] == "test-scheduler"
        assert kwargs["labels"]["expires_at"] == "2000000000"

    def test_create_translates_api_error(self, runtime, mock_docker, metadata, job_uuid):
        from docker.errors import APIError
        from shared.errors.container_runtime_errors import ContainerCreationFail
        
        mock_docker.containers.run.side_effect = APIError("Docker says no")
        
        with pytest.raises(ContainerCreationFail):
            runtime.create(job_uuid, "test-image", ["echo", "hello"], metadata)

    def test_create_raises_value_error_if_expires_at_is_none(self, runtime, job_uuid):
        from shared.container_runtimes.runtime_dc import RuntimeMetadata
        bad_metadata = RuntimeMetadata(managed_by="test", expires_at=None)
        
        with pytest.raises(ValueError, match="expires_at is required"):
            runtime.create(job_uuid, "test-image", ["echo"], bad_metadata)


    # ── remove ────────────────────────────────────────────────────────────────

    def test_remove_waits_and_forces_removal(self, runtime, mock_docker, job_uuid):
        mock_container = MagicMock()
        mock_docker.containers.get.return_value = mock_container
        
        runtime.remove(job_uuid)
        
        mock_docker.containers.get.assert_called_once_with(job_uuid)
        mock_container.wait.assert_called_once()
        mock_container.remove.assert_called_once_with(force=True)

    def test_remove_translates_not_found(self, runtime, mock_docker, job_uuid):
        from docker.errors import NotFound
        from shared.errors.container_runtime_errors import ContainerNotFound
        
        # docker.errors.NotFound requires a message arg, but the exception itself can just be raised
        mock_docker.containers.get.side_effect = NotFound("Container not found")
        
        with pytest.raises(ContainerNotFound):
            runtime.remove(job_uuid)

    def test_remove_ignores_409_conflict(self, runtime, mock_docker, job_uuid):
        """A 409 means removal is already in progress, which should be ignored."""
        from docker.errors import APIError
        import requests
        
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 409
        mock_docker.containers.get.side_effect = APIError("Conflict", response=mock_response)
        
        # Should not raise
        runtime.remove(job_uuid)


    # ── stream_file ───────────────────────────────────────────────────────────

    def test_stream_file_writes_to_archive(self, runtime, mock_docker, job_uuid, tmp_path):
        # Setup mock stream
        mock_stream = [b"chunk1", b"chunk2"]
        mock_docker.api.get_archive.return_value = (mock_stream, {"name": "stat"})
        
        out_file = tmp_path / "archive.tar"
        
        runtime.stream_file(job_uuid, "/app/dist", str(out_file))
        
        mock_docker.api.get_archive.assert_called_once_with(job_uuid, "/app/dist")
        
        with open(out_file, "rb") as f:
            content = f.read()
        assert content == b"chunk1chunk2"

    def test_stream_file_translates_not_found(self, runtime, mock_docker, job_uuid, tmp_path):
        from docker.errors import NotFound
        from shared.errors.container_runtime_errors import OutputDirNotFound
        
        mock_docker.api.get_archive.side_effect = NotFound("Path not found")
        
        with pytest.raises(OutputDirNotFound):
            runtime.stream_file(job_uuid, "/app/dist", str(tmp_path / "out.tar"))


    # ── get_container_log ─────────────────────────────────────────────────────

    def test_get_container_log_yields_lines(self, runtime, mock_docker, job_uuid):
        mock_container = MagicMock()
        mock_docker.containers.get.return_value = mock_container
        mock_container.logs.return_value = [b"log line 1\n", b"log line 2\n"]
        
        generator = runtime.get_container_log(job_uuid)
        lines = list(generator)
        
        assert lines == [b"log line 1\n", b"log line 2\n"]
        mock_container.logs.assert_called_once_with(
            stream=True, follow=True, stdout=True, stderr=True, timestamps=True
        )


    # ── list_managed_containers ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_managed_containers_count_true(self, runtime, mock_docker):
        from shared.container_runtimes.runtime_dc import RuntimeMetadata
        
        mock_docker.containers.list.return_value = [MagicMock(), MagicMock()]
        meta = RuntimeMetadata(managed_by="vire", expires_at=None)
        
        count = await runtime.list_managed_containers(meta, count=True)
        assert count == 2
        
        mock_docker.containers.list.assert_called_once()
        kwargs = mock_docker.containers.list.call_args[1]
        assert kwargs["filters"]["label"] == ["managed_by=vire"]

    @pytest.mark.asyncio
    async def test_list_managed_containers_count_false(self, runtime, mock_docker):
        from shared.container_runtimes.runtime_dc import RuntimeMetadata
        
        c1 = MagicMock(); c1.name = "job-1"
        c2 = MagicMock(); c2.name = "job-2"
        mock_docker.containers.list.return_value = [c1, c2]
        meta = RuntimeMetadata(managed_by="vire", expires_at=None)
        
        async_gen = await runtime.list_managed_containers(meta, count=False)
        
        names = []
        async for name in async_gen:
            names.append(name)
            
        assert names == ["job-1", "job-2"]


    # ── list_expired_containers ───────────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("shared.container_runtimes.runtimes.docker_runtime.time.time")
    async def test_list_expired_containers(self, mock_time, runtime, mock_docker):
        from shared.container_runtimes.runtime_dc import RuntimeMetadata
        
        mock_time.return_value = 1000  # "now" is 1000
        
        # c1 expired (950 <= 1000 - 15)
        c1 = MagicMock()
        c1.name = "job-1"
        c1.labels = {"expires_at": "950"}
        
        # c2 not expired (1000 is not <= 1000 - 15)
        c2 = MagicMock()
        c2.name = "job-2"
        c2.labels = {"expires_at": "1000"}
        
        mock_docker.containers.list.return_value = [c1, c2]
        meta = RuntimeMetadata(managed_by="vire", expires_at=None)
        
        async_gen = runtime.list_expired_containers(meta)
        
        expired = []
        async for name in async_gen:
            expired.append(name)
            
        assert expired == ["job-1"]
