"""
Pytest configuration and shared fixtures for the Vire test suite.

Environment bootstrap:
  All state.py modules read environment variables at import time.
  We set the required env vars here before any imports occur, using
  pytest's monkeypatch or os.environ directly.

  Variables set here must cover every module that has top-level
  os.environ[] reads (will raise KeyError on import otherwise):
    - CORE_ID
    - CANCELLABLE
    - CONTAINER_RUNTIME
    - REDIS_URL
    - DB_PATH / DB_URL
    - PYTHON_BIN_PATH / WORKER_PACKAGE_LOCATION
    - MAX_BUILDS_NUMBER / CONTAINER_REMOVAL_DELAY
    - AVAILABLE_FRAMEWORKS
    - CORE_LOGDIR
    - LOG_LEVEL
    - GC_LOGDIR
    - WORKER_OUTPUT_DIR / WORKER_LOGDIR
"""

import os
import tempfile
import uuid

import pytest

# ── Set up required environment variables BEFORE any app imports ───────────────
# These must be set at module level so state.py files see them during collection.

from unittest.mock import MagicMock
try:
    import docker
    docker.from_env = MagicMock()
except ImportError:
    pass

_tmp_dir = tempfile.mkdtemp(prefix="vire_test_")

os.environ.setdefault("CORE_ID", "vire-test-core")
os.environ.setdefault("CANCELLABLE", "queued,running")
os.environ.setdefault("CONTAINER_RUNTIME", "docker")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("DB_PATH", os.path.join(_tmp_dir, "test.db"))
os.environ.setdefault("DB_URL", f"sqlite+aiosqlite:///{os.path.join(_tmp_dir, 'test.db')}")
os.environ.setdefault("PYTHON_BIN_PATH", "/usr/bin/python3")
os.environ.setdefault("WORKER_PACKAGE_LOCATION", "BuildScheduler.worker.worker")
os.environ.setdefault("MAX_BUILDS_NUMBER", "5")
os.environ.setdefault("CONTAINER_REMOVAL_DELAY", "300")
os.environ.setdefault("AVAILABLE_FRAMEWORKS", "vite,")
os.environ.setdefault("CORE_LOGDIR", os.path.join(_tmp_dir, "logs"))
os.environ.setdefault("LOG_LEVEL", "info")
os.environ.setdefault("GC_LOGDIR", os.path.join(_tmp_dir, "gc_logs"))
os.environ.setdefault("WORKER_OUTPUT_DIR", os.path.join(_tmp_dir, "worker_output"))
os.environ.setdefault("WORKER_LOGDIR", os.path.join(_tmp_dir, "worker_logs"))

# Ensure all required directories exist
for _d in (
    os.environ["CORE_LOGDIR"],
    os.environ["GC_LOGDIR"],
    os.environ["WORKER_OUTPUT_DIR"],
    os.environ["WORKER_LOGDIR"],
):
    os.makedirs(_d, exist_ok=True)


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def job_uuid() -> str:
    """Return a fresh UUID4 string for use as a job_uuid."""
    return str(uuid.uuid4())


@pytest.fixture
def user_uuid() -> str:
    """Return a fresh UUID4 string for use as a user_uuid."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_build_request(job_uuid, user_uuid) -> dict:
    """
    A complete, valid build request payload matching BuildRequestModel.
    """
    return {
        "job_uuid": job_uuid,
        "user_uuid": user_uuid,
        "remote_link": "https://github.com/acme/frontend.git",
        "commit_id": "deadbeef1234567890abcdef",
        "provider": "github",
        "remote_user": "acme",
        "remote_reponame": "frontend",
        "branch": "main",
    }


@pytest.fixture
def sample_parsed_toml():
    """A valid ParsedTOMLObject for testing."""
    from Vire.objects.validation_models import ParsedTOMLObject
    return ParsedTOMLObject(
        framework="vite",
        package_manager="npm",
        framework_version="5.0.0",
        output_dir="dist",
        install_req=True,
    )


@pytest.fixture
def sample_worker_context(job_uuid, user_uuid):
    """A valid WorkerContext for testing worker-related code."""
    from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
    return WorkerContext(
        job_uuid=job_uuid,
        user_uuid=user_uuid,
        remote="https://github.com/acme/frontend.git",
        repo_name="frontend",
        framework="vite",
        package_manager="npm",
        install_req=True,
        OUTPUT_DIR="dist",
        COMMIT_ID="deadbeef1234",
    )


@pytest.fixture
def sample_worker_creation_params(job_uuid, user_uuid):
    """A valid WorkerCreationParams for scheduler tests."""
    from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams
    return WorkerCreationParams(
        job_uuid=job_uuid,
        user_uuid=user_uuid,
        remote_link="https://github.com/acme/frontend.git",
        commit_id="deadbeef1234",
        repo_name="frontend",
        framework="vite",
        pm="npm",
        install_req=True,
        output_dir="dist",
    )
 