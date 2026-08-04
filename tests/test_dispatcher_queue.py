"""
Integration tests for BuildScheduler/Scheduler/core/dispatch_from_queue.py
and related queue/locking primitives.

Covers:
  - dispatch_queued_job — drains the asyncio queue and launches workers
  - dispatch_queued_job with available_slots <= 0 returns early
  - get_worker_count — delegates to the runtime adapter
  - launch_workers — creates async tasks for each job_uuid
  - Queue state after dispatch (jobs consumed, correct count)

Docker (ContainerRuntime) is mocked at the RUNTIME_REGISTRY boundary.
scheduler_create_worker is mocked so we don't spin real processes.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_LOGGER = "shared.logging.scheduler_logger.vire_logger"
PATCH_REDIS  = "shared.logging.pub_redis.publish_log_redis"


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def job_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def user_uuid():
    return str(uuid.uuid4())


@pytest.fixture(autouse=True)
def patch_externals():
    with patch(PATCH_LOGGER), patch(PATCH_REDIS):
        yield


@pytest.fixture(autouse=True)
def drain_queue():
    """Drain the shared db_build_queue before and after each test."""
    from BuildScheduler.Scheduler.utils import queues

    while not queues.db_build_queue.empty():
        queues.db_build_queue.get_nowait()
    yield
    while not queues.db_build_queue.empty():
        queues.db_build_queue.get_nowait()


# ── dispatch_queued_job tests ─────────────────────────────────────────────────

class TestDispatchQueuedJob:
    """dispatch_queued_job should consume jobs from the queue and launch workers."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_slots_available(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job

        result = await dispatch_queued_job(available_slots=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_negative_slots(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job

        result = await dispatch_queued_job(available_slots=-5)
        assert result is None

    @pytest.mark.asyncio
    async def test_consumes_jobs_from_queue(self):
        """
        When jobs are in the queue and slots are available,
        dispatch_queued_job should remove them from the queue.
        """
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job
        from BuildScheduler.Scheduler.utils import queues

        # Put 3 jobs in the queue
        job1, job2, job3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        for j in (job1, job2, job3):
            await queues.db_build_queue.put(j)

        # Mock the worker creation so we don't spawn real processes
        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            new_callable=AsyncMock
        ):
            await dispatch_queued_job(available_slots=3)

        # Queue should now be empty
        assert queues.db_build_queue.empty()

    @pytest.mark.asyncio
    async def test_only_consumes_up_to_available_slots(self):
        """With 5 jobs in queue but only 2 slots, only 2 should be consumed."""
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job
        from BuildScheduler.Scheduler.utils import queues

        jobs = [str(uuid.uuid4()) for _ in range(5)]
        for j in jobs:
            await queues.db_build_queue.put(j)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            new_callable=AsyncMock
        ):
            await dispatch_queued_job(available_slots=2)

        # 3 jobs should remain in the queue
        remaining = []
        while not queues.db_build_queue.empty():
            remaining.append(queues.db_build_queue.get_nowait())

        assert len(remaining) == 3

    @pytest.mark.asyncio
    async def test_correct_job_uuids_passed_to_worker_creation(self):
        """Verify scheduler_create_worker is called with the correct job_uuids."""
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job
        from BuildScheduler.Scheduler.utils import queues

        job1 = str(uuid.uuid4())
        await queues.db_build_queue.put(job1)

        created_jobs = []

        async def mock_create_worker(job_uuid):
            created_jobs.append(job_uuid)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            side_effect=mock_create_worker
        ):
            await dispatch_queued_job(available_slots=1)

        assert job1 in created_jobs

    @pytest.mark.asyncio
    async def test_empty_queue_with_slots_does_nothing(self):
        """If there are slots but no queued jobs, no workers should be launched."""
        from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job

        created_jobs = []

        async def mock_create_worker(job_uuid):
            created_jobs.append(job_uuid)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            side_effect=mock_create_worker
        ):
            await dispatch_queued_job(available_slots=5)

        assert created_jobs == []


# ── get_worker_count tests ────────────────────────────────────────────────────

class TestGetWorkerCount:
    """get_worker_count queries the runtime registry for managed container count."""

    @pytest.mark.asyncio
    async def test_returns_integer_count_from_runtime(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import get_worker_count

        mock_runtime = MagicMock()
        mock_runtime.list_managed_containers = AsyncMock(return_value=3)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.RUNTIME_REGISTRY",
            {"docker": lambda: mock_runtime},
        ):
            result = await get_worker_count()

        assert result == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_containers(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import get_worker_count

        mock_runtime = MagicMock()
        mock_runtime.list_managed_containers = AsyncMock(return_value=0)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.RUNTIME_REGISTRY",
            {"docker": lambda: mock_runtime},
        ):
            result = await get_worker_count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_raises_value_error_when_runtime_returns_non_integer(self):
        """If list_managed_containers returns a non-int, ValueError should propagate."""
        from BuildScheduler.Scheduler.core.dispatch_from_queue import get_worker_count

        mock_runtime = MagicMock()
        # Returning a generator (async) instead of int when count=True is invalid
        mock_runtime.list_managed_containers = AsyncMock(return_value="not-an-int")

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.RUNTIME_REGISTRY",
            {"docker": lambda: mock_runtime},
        ):
            with pytest.raises(ValueError):
                await get_worker_count()


# ── launch_workers tests ──────────────────────────────────────────────────────

class TestLaunchWorkers:
    """launch_workers creates one asyncio.Task per job_uuid."""

    @pytest.mark.asyncio
    async def test_launches_one_task_per_job(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import launch_workers

        job_uuids = [str(uuid.uuid4()) for _ in range(4)]
        called_with = []

        async def mock_create_worker(job_uuid):
            called_with.append(job_uuid)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            side_effect=mock_create_worker,
        ):
            await launch_workers(job_uuids)

        assert sorted(called_with) == sorted(job_uuids)

    @pytest.mark.asyncio
    async def test_empty_list_does_nothing(self):
        from BuildScheduler.Scheduler.core.dispatch_from_queue import launch_workers

        called_with = []

        async def mock_create_worker(job_uuid):
            called_with.append(job_uuid)

        with patch(
            "BuildScheduler.Scheduler.core.dispatch_from_queue.scheduler_create_worker",
            side_effect=mock_create_worker,
        ):
            await launch_workers([])

        assert called_with == []


# ── scheduler queue/lock primitives ──────────────────────────────────────────

class TestQueueLockPrimitives:
    """Verify the shared asyncio primitives behave as expected."""

    def test_db_build_queue_is_asyncio_queue(self):
        from BuildScheduler.Scheduler.utils.queues import db_build_queue
        assert isinstance(db_build_queue, asyncio.Queue)

    def test_scheduler_lock_is_asyncio_lock(self):
        from BuildScheduler.Scheduler.utils.mutex_locks import scheduler_lock
        assert isinstance(scheduler_lock, asyncio.Lock)

    def test_queue_insert_lock_is_asyncio_lock(self):
        from BuildScheduler.Scheduler.utils.mutex_locks import queue_insert_lock
        assert isinstance(queue_insert_lock, asyncio.Lock)

    def test_job_status_locks_creates_new_lock_per_key(self):
        from BuildScheduler.Scheduler.utils.mutex_locks import job_status_locks

        lock1 = job_status_locks["job-aaa"]
        lock2 = job_status_locks["job-bbb"]

        assert lock1 is not lock2
        assert isinstance(lock1, asyncio.Lock)

    def test_job_status_locks_same_key_returns_same_lock(self):
        from BuildScheduler.Scheduler.utils.mutex_locks import job_status_locks

        key = str(uuid.uuid4())
        assert job_status_locks[key] is job_status_locks[key]

    @pytest.mark.asyncio
    async def test_queue_put_and_get_preserve_order(self):
        """The asyncio.Queue is FIFO — items should come out in insertion order."""
        from BuildScheduler.Scheduler.utils import queues

        job1, job2, job3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        for j in (job1, job2, job3):
            await queues.db_build_queue.put(j)

        got = []
        for _ in range(3):
            got.append(queues.db_build_queue.get_nowait())

        assert got == [job1, job2, job3]
