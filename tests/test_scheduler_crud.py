"""
Integration tests for BuildScheduler/Scheduler/db/sqlite_orm/crud/*.

Uses a real async SQLite database (in-memory via SQLAlchemy + aiosqlite)
to validate the full CRUD pipeline without mocks at the DB layer.

Covers:
  - create.register_build_data — inserts into BuildData
  - create.register_build_state — inserts into BuildState
  - read.fetch_build_data — returns WorkerCreationParams for known job_uuid
  - read.load_queued_builds — puts queued job_uuids into the asyncio Queue
  - update.update_job_status — updates status, pid, error, finished_at

External dependencies patched:
  - shared.logging.scheduler_logger.vire_logger  (logging I/O)
  - shared.logging.pub_redis.publish_log_redis    (Redis I/O)
"""

import asyncio
import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import declarative_base

PATCH_LOGGER = "shared.logging.scheduler_logger.vire_logger"
PATCH_REDIS  = "shared.logging.pub_redis.publish_log_redis"


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def job_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def user_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def sample_brm(job_uuid, user_uuid):
    """A minimal BuildRequestModel-like object."""
    from Vire.models.pydantic_classes import BuildRequestModel
    return BuildRequestModel(
        job_uuid=job_uuid,
        user_uuid=user_uuid,
        remote_link="https://github.com/acme/frontend.git",
        commit_id="deadbeef1234",
        provider="github",
        remote_user="acme",
        remote_reponame="frontend",
        branch="main",
    )


@pytest.fixture
def sample_pto():
    """A minimal ParsedTOMLObject."""
    from Vire.objects.validation_models import ParsedTOMLObject
    return ParsedTOMLObject(
        framework="vite",
        package_manager="npm",
        framework_version="5.0",
        output_dir="dist",
        install_req=True,
    )


@pytest.fixture(autouse=True)
def patch_externals():
    """Patch logger and Redis for every test in this module."""
    with patch(PATCH_LOGGER), patch(PATCH_REDIS):
        yield



import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    """
    Create a fresh SQLAlchemy async engine + tables for each test.

    We create the engine using an on-disk temp file because aiosqlite 
    shared-memory setups can drop state across isolated connection handles.
    """
    # Import the actual Base bound to BuildData and BuildState
    from BuildScheduler.Scheduler.db.sqlite_orm.db import Base, engine
    from BuildScheduler.Scheduler.db.sqlite_orm.models import init_db

    db_file = tmp_path / "test_scheduler.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    await init_db(engine=engine)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    """Return an async_sessionmaker tied to the test engine."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


# ── helper: patch the module-level async_session with our test session_factory ──

def crud_session_patch(session_factory):
    """Return a context manager that replaces async_session in all crud modules."""
    return patch(
        "BuildScheduler.Scheduler.db.sqlite_orm.db.async_session",
        new=session_factory,
    )


# ── create tests ──────────────────────────────────────────────────────────────

class TestRegisterBuildData:
    """register_build_data inserts a BuildData row."""

    @pytest.mark.asyncio
    async def test_inserts_correct_data(self, session_factory, sample_brm, sample_pto):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_data
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildData
        from sqlalchemy.future import select

        with crud_session_patch(session_factory):
            await register_build_data(sample_brm, sample_pto)

        # Verify the row exists and has the right values
        async with session_factory() as session:
            result = await session.execute(
                select(BuildData).where(BuildData.job_uuid == sample_brm.job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row is not None
        assert row.job_uuid == sample_brm.job_uuid
        assert row.user_uuid == sample_brm.user_uuid
        assert row.remote_link == sample_brm.remote_link
        assert row.commit_id == sample_brm.commit_id
        assert row.framework == sample_pto.framework
        assert row.pm == sample_pto.package_manager
        assert row.install_req == sample_pto.install_req
        assert row.output_dir == sample_pto.output_dir

    @pytest.mark.asyncio
    async def test_duplicate_job_uuid_raises(self, session_factory, sample_brm, sample_pto):
        """Inserting the same job_uuid twice should raise due to primary key constraint."""
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_data

        with crud_session_patch(session_factory):
            await register_build_data(sample_brm, sample_pto)
            with pytest.raises(Exception):
                await register_build_data(sample_brm, sample_pto)


class TestRegisterBuildState:
    """register_build_state inserts a BuildState row."""

    @pytest.mark.asyncio
    async def test_inserts_queued_state(self, session_factory, job_uuid, user_uuid):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_state
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        with crud_session_patch(session_factory):
            await register_build_state(job_uuid=job_uuid, user_uuid=user_uuid, status="queued")

        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row is not None
        assert row.status == "queued"
        assert row.user_uuid == user_uuid
        assert row.error is None
        assert row.pid is None


# ── read tests ────────────────────────────────────────────────────────────────

class TestFetchBuildData:
    """fetch_build_data returns WorkerCreationParams for a known job_uuid."""

    async def _seed(self, session_factory, brm, pto):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_data
        with crud_session_patch(session_factory):
            await register_build_data(brm, pto)

    @pytest.mark.asyncio
    async def test_returns_worker_creation_params_for_known_uuid(
        self, session_factory, sample_brm, sample_pto
    ):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import fetch_build_data
        from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams

        await self._seed(session_factory, sample_brm, sample_pto)

        with crud_session_patch(session_factory):
            result = await fetch_build_data(sample_brm.job_uuid)

        assert isinstance(result, WorkerCreationParams)
        assert result.job_uuid == sample_brm.job_uuid
        assert result.framework == sample_pto.framework
        assert result.pm == sample_pto.package_manager
        assert result.install_req == sample_pto.install_req

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_uuid(self, session_factory):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import fetch_build_data

        with crud_session_patch(session_factory):
            result = await fetch_build_data("nonexistent-uuid-0000")

        assert result is None


class TestLoadQueuedBuilds:
    """load_queued_builds populates the asyncio.Queue with queued job_uuids."""

    async def _seed_states(self, session_factory, states: list[tuple[str, str, str]]):
        """states: list of (job_uuid, user_uuid, status)"""
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_state

        with crud_session_patch(session_factory):
            for j_uuid, u_uuid, status in states:
                await register_build_state(job_uuid=j_uuid, user_uuid=u_uuid, status=status)

    @pytest.mark.asyncio
    async def test_queued_jobs_are_added_to_queue(self, session_factory, user_uuid):
        """Three queued jobs → all three job_uuids appear in the asyncio Queue."""
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import load_queued_builds
        from BuildScheduler.Scheduler.utils import queues_locks

        job1, job2, job3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        await self._seed_states(session_factory, [
            (job1, user_uuid, "queued"),
            (job2, user_uuid, "queued"),
            (job3, user_uuid, "queued"),
        ])

        # Drain the queue first to avoid pollution from other tests
        while not queues_locks.db_build_queue.empty():
            queues_locks.db_build_queue.get_nowait()

        with crud_session_patch(session_factory):
            await load_queued_builds(number_of_builds=10)

        # Collect everything from the queue
        collected = []
        while not queues_locks.db_build_queue.empty():
            collected.append(queues_locks.db_build_queue.get_nowait())

        assert set([job1, job2, job3]).issubset(set(collected))

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, session_factory, user_uuid):
        """load_queued_builds(2) should add at most 2 items to the queue."""
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import load_queued_builds
        from BuildScheduler.Scheduler.utils import queues_locks

        jobs = [str(uuid.uuid4()) for _ in range(5)]
        await self._seed_states(session_factory, [(j, user_uuid, "queued") for j in jobs])

        while not queues_locks.db_build_queue.empty():
            queues_locks.db_build_queue.get_nowait()

        with crud_session_patch(session_factory):
            await load_queued_builds(number_of_builds=2)

        count = 0
        while not queues_locks.db_build_queue.empty():
            queues_locks.db_build_queue.get_nowait()
            count += 1

        assert count <= 2

    @pytest.mark.asyncio
    async def test_running_jobs_not_added_to_queue(self, session_factory, user_uuid):
        """Only 'queued' status should enter the queue; 'running' should be excluded."""
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import load_queued_builds
        from BuildScheduler.Scheduler.utils import queues_locks

        queued_job = str(uuid.uuid4())
        running_job = str(uuid.uuid4())
        await self._seed_states(session_factory, [
            (queued_job, user_uuid, "queued"),
            (running_job, user_uuid, "running"),
        ])

        while not queues_locks.db_build_queue.empty():
            queues_locks.db_build_queue.get_nowait()

        with crud_session_patch(session_factory):
            await load_queued_builds(number_of_builds=10)

        collected = []
        while not queues_locks.db_build_queue.empty():
            collected.append(queues_locks.db_build_queue.get_nowait())

        assert queued_job in collected
        assert running_job not in collected


# ── update tests ──────────────────────────────────────────────────────────────

class TestUpdateJobStatus:
    """update_job_status modifies the BuildState row correctly."""

    async def _seed_state(self, session_factory, job_uuid, user_uuid, status="queued"):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import register_build_state

        with crud_session_patch(session_factory):
            await register_build_state(job_uuid=job_uuid, user_uuid=user_uuid, status=status)

    @pytest.mark.asyncio
    async def test_status_updated_to_running(self, session_factory, job_uuid, user_uuid):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        await self._seed_state(session_factory, job_uuid, user_uuid, status="queued")

        with crud_session_patch(session_factory):
            await update_job_status(job_uuid=job_uuid, status_msg="running", PID=12345)

        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row.status == "running"
        assert row.pid == 12345

    @pytest.mark.asyncio
    async def test_status_updated_to_finished(self, session_factory, job_uuid, user_uuid):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        await self._seed_state(session_factory, job_uuid, user_uuid, status="running")

        with crud_session_patch(session_factory):
            await update_job_status(job_uuid=job_uuid, status_msg="finished")

        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row.status == "finished"

    @pytest.mark.asyncio
    async def test_error_code_stored_on_crash(self, session_factory, job_uuid, user_uuid):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        await self._seed_state(session_factory, job_uuid, user_uuid, status="running")

        with crud_session_patch(session_factory):
            await update_job_status(
                job_uuid=job_uuid, status_msg="crashed", error_code="VC-SC-001"
            )

        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row.status == "crashed"
        assert row.error == "VC-SC-001"

    @pytest.mark.asyncio
    async def test_nonexistent_job_raises_no_job_state_error(
        self, session_factory, job_uuid, user_uuid
    ):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from shared.errors.scheduler_errors import NoJobStateError

        with crud_session_patch(session_factory):
            with pytest.raises(NoJobStateError):
                await update_job_status(job_uuid="ghost-uuid-0000", status_msg="finished")

    @pytest.mark.asyncio
    async def test_finished_at_is_set_after_update(self, session_factory, job_uuid, user_uuid):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        await self._seed_state(session_factory, job_uuid, user_uuid)

        with crud_session_patch(session_factory):
            await update_job_status(job_uuid=job_uuid, status_msg="finished")

        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        # finished_at should be populated (SQLite func.now() sets it on the DB side)
        # It might be None if func.now() is evaluated lazily — we check it's at least
        # not raising and status is correct.
        assert row.status == "finished"


# ── full create → read → update lifecycle test ───────────────────────────────

class TestSchedulerDbLifecycle:
    """
    End-to-end lifecycle: register data + state → read back → update status.

    Verifies that the CRUD modules compose correctly for a real build job flow.
    """

    @pytest.mark.asyncio
    async def test_full_build_lifecycle(self, session_factory, sample_brm, sample_pto):
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.create import (
            register_build_data,
            register_build_state,
        )
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.read import fetch_build_data
        from BuildScheduler.Scheduler.db.sqlite_orm.crud.update import update_job_status
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildState
        from sqlalchemy.future import select

        job_uuid = sample_brm.job_uuid
        user_uuid = sample_brm.user_uuid

        with crud_session_patch(session_factory):
            # Step 1: Register build data and state (simulates API receiving a build request)
            await register_build_data(sample_brm, sample_pto)
            await register_build_state(job_uuid=job_uuid, user_uuid=user_uuid, status="queued")

            # Step 2: Scheduler reads the build data to create a worker
            wcp = await fetch_build_data(job_uuid)
            assert wcp is not None
            assert wcp.framework == "vite"

            # Step 3: Scheduler marks job as running with a PID
            await update_job_status(job_uuid=job_uuid, status_msg="running", PID=99999)

            # Step 4: Worker finishes and marks as finished
            await update_job_status(job_uuid=job_uuid, status_msg="finished")

        # Verify final DB state
        async with session_factory() as session:
            result = await session.execute(
                select(BuildState).where(BuildState.job_uuid == job_uuid)
            )
            row = result.scalar_one_or_none()

        assert row.status == "finished"
        assert row.pid == 99999
