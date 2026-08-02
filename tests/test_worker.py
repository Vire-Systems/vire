import os
import sqlite3
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.worker import main, complete_final_tasks, init
from BuildScheduler.worker.core.create_container_job import setup_creation
from BuildScheduler.worker.utils.state import worker_config
from shared.errors.container_runtime_errors import ContainerCreationFail, OutputDirNotFound

# --- Fixtures ---

@pytest.fixture
def worker_db():
    """Initializes the BuildState table in the test database."""
    db_path = worker_config.DB_FILE
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS BuildState (
            job_uuid TEXT,
            user_uuid TEXT,
            status TEXT
        )
    ''')
    cursor.execute('DELETE FROM BuildState')
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def running_job(worker_db, job_uuid, user_uuid):
    """Inserts a mock 'running' job for the worker to update."""
    cursor = worker_db.cursor()
    cursor.execute('INSERT INTO BuildState (job_uuid, user_uuid, status) VALUES (?, ?, ?)', (job_uuid, user_uuid, 'running'))
    worker_db.commit()

# --- Mock Constants ---

PATCH_RUNTIME_CREATE = "shared.container_runtimes.runtimes.docker_runtime.DockerRuntime.create"
PATCH_RUNTIME_LOGS = "shared.container_runtimes.runtimes.docker_runtime.DockerRuntime.get_container_log"
PATCH_RUNTIME_STREAM = "shared.container_runtimes.runtimes.docker_runtime.DockerRuntime.stream_file"
PATCH_RUNTIME_REMOVE = "shared.container_runtimes.runtimes.docker_runtime.DockerRuntime.remove"
PATCH_REDIS_PUB = "BuildScheduler.worker.core.create_container_job.publish_log_redis"
PATCH_DISPATCH_WORKER = "BuildScheduler.worker.worker.dispatch_event"
PATCH_DISPATCH_CREATE = "BuildScheduler.worker.core.create_container_job.dispatch_event"
PATCH_DISPATCH_CLEANUP = "BuildScheduler.worker.core.cleanup_container.dispatch_event"

# --- Tests ---

class TestWorkerIntegration:
    
    def test_setup_creation_generates_correct_commands(self, sample_worker_context):
        """Verifies correct build image and bash commands are formulated."""
        image, cmd = setup_creation(sample_worker_context)
        assert image == "vire-runner:node22"
        # Check command has clone, checkout, install, and build
        assert "git clone https://github.com/acme/frontend.git" in cmd
        assert "git checkout deadbeef1234" in cmd
        assert "npm ci" in cmd
        assert "npm run build" in cmd

    @pytest.mark.asyncio
    async def test_worker_main_success_flow(self, sample_worker_context, running_job, worker_db):
        """Test full successful execution of a worker job."""
        
        def mock_log_generator(*args, **kwargs):
            yield b"log line 1\n"
            yield b"log line 2\n"

        with patch(PATCH_RUNTIME_CREATE) as mock_create, \
             patch(PATCH_RUNTIME_LOGS) as mock_logs, \
             patch(PATCH_RUNTIME_STREAM) as mock_stream, \
             patch(PATCH_RUNTIME_REMOVE) as mock_remove, \
             patch(PATCH_REDIS_PUB, new_callable=AsyncMock) as mock_redis:
            
            mock_logs.return_value = mock_log_generator()
            
            await main(sample_worker_context)
            
            mock_create.assert_called_once()
            mock_stream.assert_called_once()
            mock_remove.assert_called_once()
            assert mock_redis.call_count == 2
            
            # Check DB status transitioned from running -> finished
            cursor = worker_db.cursor()
            status = cursor.execute('SELECT status FROM BuildState WHERE job_uuid=?', (sample_worker_context.job_uuid,)).fetchone()[0]
            assert status == "finished"

    @pytest.mark.asyncio
    async def test_worker_main_container_creation_fails_crashed(self, sample_worker_context, running_job, worker_db):
        """Test worker handles container creation failure and marks job as crashed."""
        
        with patch(PATCH_RUNTIME_CREATE, side_effect=ContainerCreationFail(error_title="Failed to create container")) as mock_create, \
             patch(PATCH_DISPATCH_CREATE, new_callable=AsyncMock) as mock_dispatch_create, \
             patch(PATCH_DISPATCH_WORKER, new_callable=AsyncMock) as mock_dispatch_worker, \
             patch(PATCH_RUNTIME_STREAM, side_effect=Exception("No container to stream from")) as mock_stream, \
             patch(PATCH_RUNTIME_REMOVE) as mock_remove:
             
            await main(sample_worker_context)
            
            mock_create.assert_called_once()
            
            # Event dispatch gets called twice:
            # 1. By container_create catching ContainerCreationFail (PATCH_DISPATCH_CREATE)
            # 2. By main catching Exception when stream_file propagates it up (PATCH_DISPATCH_WORKER)
            assert mock_dispatch_create.call_count == 1
            assert mock_dispatch_worker.call_count == 1
            
            # Check DB status is 'crashed' due to transition_job_state catching Exception
            cursor = worker_db.cursor()
            status = cursor.execute('SELECT status FROM BuildState WHERE job_uuid=?', (sample_worker_context.job_uuid,)).fetchone()[0]
            assert status == "crashed"

    @pytest.mark.asyncio
    async def test_worker_main_cancelled_job_skips_stream(self, sample_worker_context, worker_db):
        """Test if job is marked cancelled, worker skips streaming but still cleans up."""
        cursor = worker_db.cursor()
        cursor.execute('INSERT INTO BuildState (job_uuid, user_uuid, status) VALUES (?, ?, ?)', (sample_worker_context.job_uuid, sample_worker_context.user_uuid, 'cancelled'))
        worker_db.commit()

        def mock_log_generator(*args, **kwargs):
            yield b"log line\n"

        with patch(PATCH_RUNTIME_CREATE) as mock_create, \
             patch(PATCH_RUNTIME_LOGS) as mock_logs, \
             patch(PATCH_RUNTIME_STREAM) as mock_stream, \
             patch(PATCH_RUNTIME_REMOVE) as mock_remove, \
             patch(PATCH_REDIS_PUB, new_callable=AsyncMock):
            
            mock_logs.return_value = mock_log_generator()
            
            await main(sample_worker_context)
            
            # Stream should not be called because status is cancelled
            mock_stream.assert_not_called()
            
            # Remove should still be called to clean up
            mock_remove.assert_called_once()
            
            # Status should remain cancelled
            cursor = worker_db.cursor()
            status = cursor.execute('SELECT status FROM BuildState WHERE job_uuid=?', (sample_worker_context.job_uuid,)).fetchone()[0]
            assert status == "cancelled"

    @pytest.mark.asyncio
    async def test_worker_main_output_dir_not_found(self, sample_worker_context, running_job, worker_db):
        """Test worker handles OutputDirNotFound during stream_file."""
        
        def mock_log_generator(*args, **kwargs):
            yield b"build succeeded but dist folder is missing\n"

        with patch(PATCH_RUNTIME_CREATE) as mock_create, \
             patch(PATCH_RUNTIME_LOGS) as mock_logs, \
             patch(PATCH_RUNTIME_STREAM, side_effect=OutputDirNotFound(error_title="Cannot find dist")) as mock_stream, \
             patch(PATCH_RUNTIME_REMOVE) as mock_remove, \
             patch(PATCH_DISPATCH_WORKER, new_callable=AsyncMock) as mock_dispatch_worker, \
             patch(PATCH_REDIS_PUB, new_callable=AsyncMock):
            
            mock_logs.return_value = mock_log_generator()
            
            await main(sample_worker_context)
            
            mock_create.assert_called_once()
            mock_stream.assert_called_once()
            mock_remove.assert_called_once()
            
            # stream_file should catch OutputDirNotFound and dispatch an error event
            mock_dispatch_worker.assert_called_once()
            args, kwargs = mock_dispatch_worker.call_args
            assert kwargs["event"].error.error_title == "Cannot find dist"
            
            # Because OutputDirNotFound is caught and not re-raised in stream_file,
            # main() continues, remove_container() completes, and state is transitioned to finished!
            cursor = worker_db.cursor()
            status = cursor.execute('SELECT status FROM BuildState WHERE job_uuid=?', (sample_worker_context.job_uuid,)).fetchone()[0]
            assert status == "finished"
