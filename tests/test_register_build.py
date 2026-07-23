"""
Integration tests for Vire/core/register_with_queue.py

Covers:
  - register_build success path (validating -> passed)
  - register_build failure path (validating -> failed) due to validation error
  - register_build unexpected error path (dispatch event)

External dependencies patched:
  - validate_details (simulating network/validation pass/fail)
  - register_job_with_redis (Redis is external)
  - shared.logging.scheduler_logger.vire_logger
  - shared.logging.pub_redis.publish_log_redis
"""

from unittest.mock import AsyncMock, patch

import pytest


PATCH_LOGGER = "shared.logging.scheduler_logger.vire_logger"
PATCH_REDIS_PUB = "shared.logging.pub_redis.publish_log_redis"
PATCH_REDIS_REG = "Vire.core.register_with_queue.register_job_with_redis"
PATCH_VALIDATE = "Vire.core.register_with_queue.validate_details"

# ── DB setup for realistic CRUD integration ───────────────────────────────────

@pytest.fixture
async def db_engine(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine
    from BuildScheduler.Scheduler.db.sqlite_orm.models import Base

    db_file = tmp_path / "test_register.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


def crud_session_patch(session_factory):
    return patch(
        "BuildScheduler.Scheduler.db.sqlite_orm.crud.create.async_session",
        new=session_factory,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegisterBuild:
    
    @pytest.mark.asyncio
    async def test_register_build_success(
        self, session_factory, sample_build_request, sample_parsed_toml
    ):
        from Vire.core.register_with_queue import register_build
        from Vire.models.pydantic_classes import BuildRequestModel
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildData, BuildState
        from sqlalchemy.future import select

        brm = BuildRequestModel(**sample_build_request)

        mock_redis_reg = AsyncMock()
        mock_validate = AsyncMock(return_value=sample_parsed_toml)

        with patch(PATCH_LOGGER), patch(PATCH_REDIS_PUB), \
             patch(PATCH_REDIS_REG, mock_redis_reg), \
             patch(PATCH_VALIDATE, mock_validate), \
             crud_session_patch(session_factory):

            result = await register_build(brm)
        assert result is True
        
        # Redis should be called twice (validating, passed)
        assert mock_redis_reg.call_count == 2
        calls = mock_redis_reg.call_args_list
        assert calls[0][0][1] == "validating"
        assert calls[1][0][1] == "passed"
        
        # Check that DB was actually updated
        async with session_factory() as session:
            data_res = await session.execute(select(BuildData).where(BuildData.job_uuid == brm.job_uuid))
            state_res = await session.execute(select(BuildState).where(BuildState.job_uuid == brm.job_uuid))
            
            row_data = data_res.scalar_one_or_none()
            row_state = state_res.scalar_one_or_none()
            
        assert row_data is not None
        assert row_state is not None
        assert row_state.status == "queued"

    @pytest.mark.asyncio
    async def test_register_build_validation_failure(
        self, session_factory, sample_build_request
    ):
        from Vire.core.register_with_queue import register_build
        from Vire.models.pydantic_classes import BuildRequestModel
        from BuildScheduler.Scheduler.db.sqlite_orm.models import BuildData

        brm = BuildRequestModel(**sample_build_request)

        mock_redis_reg = AsyncMock()
        # Simulate validation returning None (e.g. invalid TOML)
        mock_validate = AsyncMock(return_value=None)

        with patch(PATCH_LOGGER), patch(PATCH_REDIS_PUB), \
             patch(PATCH_REDIS_REG, mock_redis_reg), \
             patch(PATCH_VALIDATE, mock_validate), \
             crud_session_patch(session_factory):
            
            result = await register_build(brm)
            
        assert result is False
        
        # Redis should be called twice (validating, failed)
        assert mock_redis_reg.call_count == 2
        calls = mock_redis_reg.call_args_list
        assert calls[0][0][1] == "validating"
        assert calls[1][0][1] == "failed"
        
        # Ensure DB was NOT updated
        async with session_factory() as session:
            from sqlalchemy.future import select
            data_res = await session.execute(select(BuildData).where(BuildData.job_uuid == brm.job_uuid))
            row_data = data_res.scalar_one_or_none()
            
        assert row_data is None

    @pytest.mark.asyncio
    async def test_register_build_unexpected_error_dispatches_log(
        self, session_factory, sample_build_request
    ):
        from Vire.core.register_with_queue import register_build
        from Vire.models.pydantic_classes import BuildRequestModel
        from shared.events.events import LogEvent

        brm = BuildRequestModel(**sample_build_request)

        # Let's mock register_job_with_redis to raise an Exception
        mock_redis_reg = AsyncMock(side_effect=RuntimeError("Redis connection lost"))
        mock_dispatch = AsyncMock()

        with patch(PATCH_LOGGER), patch(PATCH_REDIS_PUB), \
             patch(PATCH_REDIS_REG, mock_redis_reg), \
             patch("Vire.core.register_with_queue.dispatch_event", mock_dispatch), \
             crud_session_patch(session_factory):
            
            result = await register_build(brm)
            
        assert result is False
        
        # dispatch_event should be called with LogEvent
        mock_dispatch.assert_called_once()
        event_arg = mock_dispatch.call_args[1]["event"]
        assert isinstance(event_arg, LogEvent)
        assert event_arg.diag_code == "VC-IN-UNEXPECTED_INTERNAL_ERROR"
        assert event_arg.exception_name == "RuntimeError"
