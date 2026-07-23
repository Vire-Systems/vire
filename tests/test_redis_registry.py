"""
Integration tests for BuildScheduler/Scheduler/db/caching/redis_registry.py.

Covers:
  - register_job_with_redis (inserts mapping into Redis hash)
  
External dependencies patched:
  - shared.logging.pub_redis.client
"""

from unittest.mock import AsyncMock, patch
import pytest

PATCH_REDIS_CLIENT = "BuildScheduler.Scheduler.db.caching.redis_registry.client"

class TestRedisRegistry:
    """Verify that register_job_with_redis calls hset with correct mapping."""

    @pytest.mark.asyncio
    async def test_register_job_with_redis_calls_hset(self, sample_build_request):
        from BuildScheduler.Scheduler.db.caching.redis_registry import register_job_with_redis
        from Vire.models.pydantic_classes import BuildRequestModel
        from shared.shared_state import shared_config

        brm = BuildRequestModel(**sample_build_request)
        
        # We mock the redis client context manager and the hset method
        mock_redis = AsyncMock()
        mock_redis.hset = AsyncMock()
        
        # Async context manager mock
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_redis
        mock_client.__aexit__.return_value = False
        
        with patch(PATCH_REDIS_CLIENT, mock_client):
            await register_job_with_redis(brm, state="validating")
            
        mock_redis.hset.assert_called_once()
        args, kwargs = mock_redis.hset.call_args
        
        expected_key = f"job_session:{brm.user_uuid}/{brm.job_uuid}"
        assert args[0] == expected_key
        
        mapping = kwargs["mapping"]
        assert mapping["core_id"] == shared_config.CORE_ID
        assert mapping["remote_user"] == brm.remote_user
        assert mapping["repo"] == brm.remote_reponame
        assert mapping["commit_id"] == brm.commit_id
        assert mapping["provider"] == brm.provider
        assert mapping["state"] == "validating"
