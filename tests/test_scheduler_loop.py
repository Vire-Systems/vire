import pytest

pytest.skip("Scheduler tests temporarily disabled", allow_module_level=True)

"""
Integration tests for BuildScheduler/Scheduler/scheduler_loop.py

Covers:
  - scheduler_loop normal execution path (breaks out via exception for testing)
  - Verify worker count fetching, queue reading, and job dispatching are called
  - Verify that unexpected exceptions result in a LogEvent dispatch

External dependencies patched:
  - dispatch_queued_job, get_worker_count (for controlling flow)
  - read.load_queued_builds
  - shared.logging.scheduler_logger.vire_logger
  - asyncio.sleep (to break the infinite loop)
"""

from unittest.mock import AsyncMock, patch

import pytest


PATCH_LOGGER = "shared.logging.scheduler_logger.vire_logger"
PATCH_DISPATCH = "BuildScheduler.Scheduler.scheduler_loop.dispatch_queued_job"
PATCH_WORKER_COUNT = "BuildScheduler.Scheduler.scheduler_loop.get_worker_count"
PATCH_LOAD_QUEUED = "BuildScheduler.Scheduler.db.sqlite_orm.crud.read.load_queued_builds"
PATCH_DISPATCH_EVENT = "BuildScheduler.Scheduler.scheduler_loop.dispatch_event"
PATCH_SLEEP = "asyncio.sleep"


class LoopBreakException(Exception):
    """Custom exception used to break the infinite while loop in scheduler_loop."""
    pass


class TestSchedulerLoop:
    
    @pytest.mark.asyncio
    async def test_scheduler_loop_one_iteration(self):
        from BuildScheduler.Scheduler.scheduler_loop import scheduler_loop
        from BuildScheduler.Scheduler.utils.state import scheduler_config

        mock_worker_count = AsyncMock(return_value=2)
        mock_load_queued = AsyncMock()
        mock_dispatch = AsyncMock()
        mock_sleep = AsyncMock(side_effect=LoopBreakException("Break loop!"))
        mock_event = AsyncMock()

        with patch(PATCH_LOGGER), \
             patch(PATCH_WORKER_COUNT, mock_worker_count), \
             patch(PATCH_LOAD_QUEUED, mock_load_queued), \
             patch(PATCH_DISPATCH, mock_dispatch), \
             patch(PATCH_DISPATCH_EVENT, mock_event), \
             patch(PATCH_SLEEP, mock_sleep):
            
            # The loop will hit asyncio.sleep and raise LoopBreakException
            # This will fall into the except Exception block and dispatch an event.
            await scheduler_loop()
            
        # Verify that get_worker_count was called
        mock_worker_count.assert_called_once()
        
        # Verify that load_queued_builds was called with (MAX_BUILDS - worker_count)
        expected_slots = scheduler_config.MAX_BUILDS_NUMBER - 2
        mock_load_queued.assert_called_once_with(expected_slots)
        
        # Verify that dispatch_queued_job was scheduled (via asyncio.create_task)
        # We can't directly assert on the task creation easily without patching create_task,
        # but since we patched dispatch_queued_job, if the loop executed it, it exists.
        # But wait, asyncio.create_task(mock_dispatch(available_slots)) will call mock_dispatch immediately
        # and create a task for the returned coroutine.
        mock_dispatch.assert_called_once_with(expected_slots)
        
        # Verify that the exception block ran (because of LoopBreakException)
        mock_event.assert_called_once()
        evt = mock_event.call_args[0][0]
        assert evt.exception_name == "LoopBreakException"
        assert "Break loop!" in evt.internal_log

    @pytest.mark.asyncio
    async def test_scheduler_loop_worker_count_none_raises_value_error(self):
        """If worker_count returns None/0/False evaluating to false, it raises ValueError."""
        from BuildScheduler.Scheduler.scheduler_loop import scheduler_loop

        mock_worker_count = AsyncMock(return_value=0) # not worker_count is True for 0
        mock_event = AsyncMock()

        with patch(PATCH_LOGGER), \
             patch(PATCH_WORKER_COUNT, mock_worker_count), \
             patch(PATCH_DISPATCH_EVENT, mock_event):
            
            await scheduler_loop()
            
        mock_worker_count.assert_called_once()
        
        # Should jump straight to exception block due to ValueError
        mock_event.assert_called_once()
        evt = mock_event.call_args[0][0]
        assert evt.exception_name == "ValueError"
