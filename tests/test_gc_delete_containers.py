"""
Integration tests for BuildScheduler/GC/core/delete_containers.py

Covers:
  - remove_single_container (success, ContainerNotFound ignored, exceptions caught)
  - batch_remove (generator exhaustion bug behavior, general flow, exception handling)

External dependencies patched:
  - shared.container_runtimes.runtime_registry.RUNTIME_REGISTRY
  - BuildScheduler.GC.core.gc_crud.get_user_uuid
  - BuildScheduler.GC.core.gc_crud.update_job_status
  - shared.event_handling.handler.dispatch_event
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.errors.container_runtime_errors import ContainerAdapterAPIError, ContainerNotFound


PATCH_RUNTIME_REGISTRY = "BuildScheduler.GC.core.delete_containers.RUNTIME_REGISTRY"
PATCH_GET_USER_UUID = "BuildScheduler.GC.core.delete_containers.get_user_uuid"
PATCH_UPDATE_JOB_STATUS = "BuildScheduler.GC.core.delete_containers.update_job_status"
PATCH_DISPATCH_EVENT = "BuildScheduler.GC.core.delete_containers.dispatch_event"
PATCH_CONFIG = "BuildScheduler.GC.core.delete_containers.shared_config"


# ── remove_single_container ───────────────────────────────────────────────────

class TestRemoveSingleContainer:

    @pytest.mark.asyncio
    async def test_remove_success_dispatches_gc_reap_event(self, job_uuid, user_uuid):
        from BuildScheduler.GC.core.delete_containers import remove_single_container
        from shared.events.events import GCReapEvent

        mock_runtime = MagicMock()
        # runtime.remove is a sync function called via asyncio.to_thread
        mock_runtime.remove = MagicMock()
        
        mock_get_user = AsyncMock(return_value=user_uuid)
        mock_dispatch = AsyncMock()
        
        # We need a custom runtime class that returns our mock_runtime
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_GET_USER_UUID, mock_get_user), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            await remove_single_container(job_uuid)
            
        mock_runtime.remove.assert_called_once_with(job_uuid=job_uuid)
        
        mock_dispatch.assert_called_once()
        evt = mock_dispatch.call_args[1]["event"]
        assert isinstance(evt, GCReapEvent)
        assert evt.job_uuid == job_uuid
        assert evt.user_uuid == user_uuid

    @pytest.mark.asyncio
    async def test_remove_container_not_found_is_ignored(self, job_uuid, user_uuid):
        from BuildScheduler.GC.core.delete_containers import remove_single_container

        mock_runtime = MagicMock()
        # Mock the remove method to raise ContainerNotFound
        mock_runtime.remove = MagicMock(side_effect=ContainerNotFound())
        
        mock_get_user = AsyncMock(return_value=user_uuid)
        mock_dispatch = AsyncMock()
        
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_GET_USER_UUID, mock_get_user), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            # Should not raise
            await remove_single_container(job_uuid)
            
        # GCReapEvent should NOT be dispatched because of the exception
        mock_dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_api_error_dispatches_log_event(self, job_uuid, user_uuid):
        from BuildScheduler.GC.core.delete_containers import remove_single_container
        from shared.events.events import LogEvent

        mock_runtime = MagicMock()
        mock_runtime.remove = MagicMock(side_effect=ContainerAdapterAPIError(error_title="Docker dead"))
        
        mock_get_user = AsyncMock(return_value=user_uuid)
        mock_dispatch = AsyncMock()
        
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_GET_USER_UUID, mock_get_user), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            await remove_single_container(job_uuid)
            
        mock_dispatch.assert_called_once()
        evt = mock_dispatch.call_args[0][0]
        assert isinstance(evt, LogEvent)
        assert evt.exception_name == "ContainerAdapterAPIError"
        assert evt.summary == "Docker dead"


# ── batch_remove ──────────────────────────────────────────────────────────────

class TestBatchRemove:
    """
    Tests for batch_remove. 
    Note: Documents the known bug where the async generator is consumed inside the loop.
    """
    
    async def _fake_generator(self, items):
        for item in items:
            yield item

    @pytest.mark.asyncio
    async def test_batch_remove_with_one_item(self):
        """
        With 1 item, the outer loop gets item_1. The inner comprehension tries to consume
        the rest, gets [], so update_job_status gets []. remove_single_container gets item_1.
        """
        from BuildScheduler.GC.core.delete_containers import batch_remove
        
        job1 = "job-1"

        mock_runtime = MagicMock()
        mock_runtime.list_expired_containers = MagicMock(return_value=self._fake_generator([job1]))
        
        mock_update = AsyncMock()
        mock_dispatch = AsyncMock()
        
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        # We mock remove_single_container so it doesn't actually run its logic
        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_UPDATE_JOB_STATUS, mock_update), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch("BuildScheduler.GC.core.delete_containers.remove_single_container", new_callable=AsyncMock) as mock_rm_single, \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            mock_cfg.CONTAINER_METADATA = {"managed_by": "test"}
            
            await batch_remove()
            
        # Due to the bug, update_job_status is called with an empty list
        mock_update.assert_called_once_with([], error_code="VC-GC-001 ")
        
        # But remove_single_container is called for the first item
        mock_rm_single.assert_called_once_with(job1)

    @pytest.mark.asyncio
    async def test_batch_remove_with_multiple_items_shows_bug(self):
        """
        With 2 items, outer loop gets job-1. Inner gets [job-2]. 
        Then generator is empty, outer loop exits. job-2 is never removed!
        """
        from BuildScheduler.GC.core.delete_containers import batch_remove
        
        job1 = "job-1"
        job2 = "job-2"

        mock_runtime = MagicMock()
        mock_runtime.list_expired_containers = MagicMock(return_value=self._fake_generator([job1, job2]))
        
        mock_update = AsyncMock()
        mock_dispatch = AsyncMock()
        
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_UPDATE_JOB_STATUS, mock_update), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch("BuildScheduler.GC.core.delete_containers.remove_single_container", new_callable=AsyncMock) as mock_rm_single, \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            mock_cfg.CONTAINER_METADATA = {"managed_by": "test"}
            
            await batch_remove()
            
        # update_job_status is called with [job-2]
        mock_update.assert_called_once_with([job2], error_code="VC-GC-001 ")
        
        # remove_single_container is ONLY called with job1
        mock_rm_single.assert_called_once_with(job1)

    @pytest.mark.asyncio
    async def test_batch_remove_exception_dispatches_event(self):
        from BuildScheduler.GC.core.delete_containers import batch_remove
        from shared.events.events import LogEvent
        
        async def broken_gen():
            raise RuntimeError("API down")
            yield
        
        mock_runtime = MagicMock()
        mock_runtime.list_expired_containers = MagicMock(return_value=broken_gen())
        
        mock_dispatch = AsyncMock()
        
        class FakeRuntime:
            def __new__(cls):
                return mock_runtime

        with patch(PATCH_RUNTIME_REGISTRY, {"docker": FakeRuntime}), \
             patch(PATCH_DISPATCH_EVENT, mock_dispatch), \
             patch(PATCH_CONFIG) as mock_cfg:
            
            mock_cfg.CONTAINER_RUNTIME = "docker"
            mock_cfg.CONTAINER_METADATA = {"managed_by": "test"}
            
            await batch_remove()
            
        mock_dispatch.assert_called_once()
        evt = mock_dispatch.call_args[0][0]
        assert isinstance(evt, LogEvent)
        assert evt.exception_name == "RuntimeError"
