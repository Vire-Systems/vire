"""
Integration tests for shared/event_handling.

Covers:
  - formatter.format_internal_log
  - formatter.format_user_report
  - handler.get_context
  - handler.dispatch_event (write_log path, propagate_state path)
  - state_propagation.send_report / propagate_state
  - ErrorEvent populates context correctly from VireBaseError
  - LogEvent log_extras wiring
  - GCReapEvent / ContainerTimeoutEvent / InfoEvent defaults

External dependencies patched:
  - shared.logging.pub_redis.publish_log_redis  (Redis I/O)
  - shared.logging.scheduler_logger.vire_logger  (logging I/O)
"""

import json
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── helpers ────────────────────────────────────────────────────────────────────

# We patch the two external side-effects for every test that exercises handler
PATCH_LOGGER = "shared.event_handling.handler.vire_logger"
PATCH_REDIS = "shared.event_handling.state_propagation.publish_log_redis"


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def job_uuid():
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

@pytest.fixture
def user_uuid():
    return "11111111-2222-3333-4444-555555555555"


# ── formatter tests ────────────────────────────────────────────────────────────

class TestFormatInternalLog:
    """format_internal_log should produce valid JSON with the expected keys."""

    def _make_context(self, job_uuid, user_uuid):
        from shared.event_handling.handler_context import EventHandlerContext
        return EventHandlerContext(
            event="TestEvent",
            timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            diag_code="VC-TEST-001",
            severity="info",
            summary="A test summary",
            job_uuid=job_uuid,
            user_uuid=user_uuid,
        )

    def test_returns_valid_json(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_internal_log

        ctx = self._make_context(job_uuid, user_uuid)
        result = format_internal_log(ctx, extra_details={})

        parsed = json.loads(result)  # must not raise
        assert isinstance(parsed, dict)

    def test_required_keys_present(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_internal_log

        ctx = self._make_context(job_uuid, user_uuid)
        parsed = json.loads(format_internal_log(ctx, extra_details={}))

        for key in ("event", "timestamp", "diag_code", "severity", "summary", "job_uuid"):
            assert key in parsed, f"Missing key: {key}"

    def test_extra_details_merged(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_internal_log

        ctx = self._make_context(job_uuid, user_uuid)
        extras = {"source": "scheduler", "exception_name": "ValueError"}
        parsed = json.loads(format_internal_log(ctx, extra_details=extras))

        assert parsed["source"] == "scheduler"
        assert parsed["exception_name"] == "ValueError"

    def test_values_match_context(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_internal_log

        ctx = self._make_context(job_uuid, user_uuid)
        parsed = json.loads(format_internal_log(ctx, extra_details={}))

        assert parsed["diag_code"] == "VC-TEST-001"
        assert parsed["severity"] == "info"
        assert parsed["summary"] == "A test summary"
        assert parsed["job_uuid"] == job_uuid


class TestFormatUserReport:
    """format_user_report should produce a multi-line human-readable string."""

    def _make_context(self, job_uuid, user_uuid, **kwargs):
        from shared.event_handling.handler_context import EventHandlerContext
        defaults: dict[str, str] = dict(
            event="ErrorEvent",
            timestamp=str(datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)),
            diag_code="VC-VD-INVALID_VIRE_TOML",
            severity="warn",
            summary="The schema of vire.toml is invalid.",
            job_uuid=job_uuid,
            user_uuid=user_uuid,
        )
        defaults.update(kwargs)
        return EventHandlerContext(**defaults)

    def test_report_contains_diag_code(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(job_uuid, user_uuid)
        report = format_user_report(ctx)

        assert "VC-VD-INVALID_VIRE_TOML" in report

    def test_report_contains_summary(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(job_uuid, user_uuid)
        report = format_user_report(ctx)

        assert "The schema of vire.toml is invalid." in report

    def test_report_severity_is_capitalised(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(job_uuid, user_uuid)
        report = format_user_report(ctx)

        # First line should be "Warn: VC-VD-INVALID_VIRE_TOML"
        first_line = report.splitlines()[0]
        assert first_line.startswith("Warn:")

    def test_possible_fixes_rendered(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(
            job_uuid, user_uuid,
            possible_fixes=("Check the docs.", "Try a fresh config.")
        )
        report = format_user_report(ctx)

        assert "Possible Fixes" in report
        assert "Check the docs." in report
        assert "Try a fresh config." in report

    def test_possible_causes_rendered(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(
            job_uuid, user_uuid,
            possible_causes=("Branch was deleted.",)
        )
        report = format_user_report(ctx)

        assert "Possible Causes" in report
        assert "Branch was deleted." in report

    def test_notes_rendered(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(
            job_uuid, user_uuid,
            notes=("Create an issue on GitHub.",)
        )
        report = format_user_report(ctx)
        assert "Note" in report
        assert "Create an issue on GitHub." in report

    def test_job_details_mapping_rendered(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(
            job_uuid, user_uuid,
            job_details={"Branch": "main", "Provider": "Github"}
        )
        report = format_user_report(ctx)

        assert "Job Details" in report
        assert "Branch: main" in report
        assert "Provider: Github" in report

    def test_empty_optional_fields_not_rendered(self, job_uuid, user_uuid):
        from shared.event_handling.formatter import format_user_report

        ctx = self._make_context(job_uuid, user_uuid)
        report = format_user_report(ctx)

        # No optional sections should appear
        assert "Possible Fixes" not in report
        assert "Possible Causes" not in report
        assert "Note" not in report


# ── event dataclass tests ─────────────────────────────────────────────────────

class TestLogEvent:
    """LogEvent should populate defaults correctly and return the right log extras."""

    def test_log_event_defaults(self, job_uuid):
        from shared.events.events import LogEvent

        evt = LogEvent(
            diag_code="VC-TEST-001",
            severity="info",
            summary="Something happened",
            source="scheduler",
            exception_name="ValueError",
            internal_log="details here",
        )
        assert evt.job_uuid == "SYSTEM"
        assert evt.user_uuid == "SYSTEM"
        assert evt.write_log is True
        assert evt.propagate_state is False

    def test_log_event_get_log_extras_includes_source(self):
        from shared.events.events import LogEvent

        evt = LogEvent(
            diag_code="VC-TEST-001",
            severity="info",
            summary="Something happened",
            source="gc",
            exception_name="RuntimeError",
            internal_log=None,
        )
        extras = evt.get_log_extras()

        assert extras["source"] == "gc"
        assert extras["exception_name"] == "RuntimeError"

    def test_log_event_internal_log_included_when_set(self):
        from shared.events.events import LogEvent

        evt = LogEvent(
            diag_code="VC-TEST-001",
            severity="info",
            summary="Something happened",
            source="gc",
            exception_name=None,
            internal_log="detailed internal message",
        )
        extras = evt.get_log_extras()
        assert "reason" in extras
        assert extras["reason"] == "detailed internal message"

    def test_log_event_internal_log_absent_when_none(self):
        from shared.events.events import LogEvent

        evt = LogEvent(
            diag_code="VC-TEST-001",
            severity="info",
            summary="Something happened",
            source="scheduler",
            exception_name=None,
            internal_log=None,
        )
        extras = evt.get_log_extras()
        assert "reason" not in extras


class TestGCReapEvent:
    def test_gc_reap_event_defaults(self, job_uuid, user_uuid):
        from shared.events.events import GCReapEvent

        evt = GCReapEvent(
            job_uuid=job_uuid,
            user_uuid=user_uuid,
            summary="Container reaped after timeout.",
        )
        assert evt.event == "ContainerReaped"
        assert evt.severity == "warn"
        assert evt.diag_code == "VC-GC-CONTAINER_REAPED"
        assert evt.write_log is True
        assert evt.propagate_state is True

    def test_gc_reap_event_timestamp_is_utc(self, job_uuid, user_uuid):
        from shared.events.events import GCReapEvent

        evt = GCReapEvent(job_uuid=job_uuid, user_uuid=user_uuid, summary="done")
        assert evt.timestamp.tzinfo is not None


class TestContainerTimeoutEvent:
    def test_container_timeout_event_defaults(self, job_uuid, user_uuid):
        from shared.events.events import ContainerTimeoutEvent

        evt = ContainerTimeoutEvent(
            job_uuid=job_uuid,
            user_uuid=user_uuid,
            summary="Container timed out. Timeout delay: 300s",
        )
        assert evt.event == "ContainerTimedOut"
        assert evt.severity == "info"
        assert evt.diag_code == "VC-SC-CONTAINER_TIMED_OUT"
        assert evt.propagate_state is True


class TestErrorEvent:
    """ErrorEvent derives diag_code/summary/severity from the wrapped VireBaseError."""

    def _make_error(self):
        from shared.errors.validation_errors import InvalidVireTomlError
        return InvalidVireTomlError(error_title="[project] table not found")

    def test_error_event_derives_diag_code_from_error(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent

        err = self._make_error()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        assert evt.diag_code == err.error_code

    def test_error_event_derives_summary_from_error(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent

        err = self._make_error()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        assert evt.summary == err.error_title

    def test_error_event_derives_severity_from_error(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent

        err = self._make_error()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        assert evt.severity == err.severity

    def test_error_event_get_extra_content_returns_error_metadata(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent
        from shared.errors.validation_errors import InvalidVireTomlError

        err = InvalidVireTomlError(
            error_title="schema wrong",
            possible_fixes=("Use the template.",),
        )
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)
        extra = evt.get_extra_content()

        assert "possible_fixes" in extra
        assert extra["possible_fixes"] == ("Use the template.",)

    def test_error_event_propagates_and_writes_log_by_default(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent

        err = self._make_error()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        assert evt.write_log is True
        assert evt.propagate_state is True


# ── handler.get_context tests ─────────────────────────────────────────────────

class TestGetContext:
    """handler.get_context should correctly populate EventHandlerContext from any VireBaseEvent."""

    def test_get_context_from_log_event(self, job_uuid):
        from shared.events.events import LogEvent
        from shared.event_handling.handler import get_context

        evt = LogEvent(
            job_uuid=job_uuid,
            diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
            severity="critical",
            summary="Something went wrong",
            source="scheduler",
            exception_name="RuntimeError",
            internal_log="details",
        )
        ctx = get_context(event=evt, job_details=None)

        assert ctx.diag_code == "VC-IN-UNEXPECTED_INTERNAL_ERROR"
        assert ctx.severity == "critical"
        assert ctx.summary == "Something went wrong"
        assert ctx.job_uuid == job_uuid

    def test_get_context_from_error_event(self, job_uuid, user_uuid):
        from shared.events.error_event import ErrorEvent
        from shared.errors.validation_errors import InvalidVireTomlError
        from shared.event_handling.handler import get_context

        err = InvalidVireTomlError(error_title="toml broken")
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)
        ctx = get_context(event=evt, job_details={"Branch": "main"})

        assert ctx.diag_code == err.error_code
        assert ctx.job_details == {"Branch": "main"}

    def test_get_context_preserves_timestamp(self, job_uuid, user_uuid):
        from shared.events.events import GCReapEvent
        from shared.event_handling.handler import get_context

        evt = GCReapEvent(job_uuid=job_uuid, user_uuid=user_uuid, summary="reaped")
        ctx = get_context(event=evt, job_details=None)

        assert ctx.timestamp == evt.timestamp


# ── handler.dispatch_event integration tests ─────────────────────────────────

class TestDispatchEvent:
    """
    dispatch_event is the central dispatcher.

    These tests verify:
      1. write_log=True events reach the logger.
      2. propagate_state=True events reach publish_log_redis (via send_report).
      3. Non-VireBaseEvent raises TypeError.
      4. ErrorEvent wrapping a non-VireBaseError raises TypeError.
    """

    @pytest.mark.asyncio
    async def test_log_event_calls_vire_logger(self, job_uuid):
        from shared.events.events import LogEvent
        from shared.event_handling.handler import dispatch_event

        evt = LogEvent(
            job_uuid=job_uuid,
            diag_code="VC-TEST-001",
            severity="info",
            summary="test log",
            source="scheduler",
            exception_name=None,
            internal_log=None,
        )

        with patch(PATCH_LOGGER) as mock_logger:
            await dispatch_event(evt)
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args
            # First positional arg is the log level
            assert call_args[0][0] == "info"

    @pytest.mark.asyncio
    async def test_log_event_does_not_propagate(self, job_uuid):
        """LogEvent.propagate_state is False by default — Redis should NOT be called."""
        from shared.events.events import LogEvent
        from shared.event_handling.handler import dispatch_event

        evt = LogEvent(
            job_uuid=job_uuid,
            diag_code="VC-TEST-001",
            severity="warn",
            summary="test log — no propagation",
            source="gc",
            exception_name=None,
            internal_log=None,
        )

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            await dispatch_event(evt)
            mock_redis.assert_not_called()

    @pytest.mark.asyncio
    async def test_gc_reap_event_propagates_to_redis(self, job_uuid, user_uuid):
        """GCReapEvent.propagate_state is True — Redis publish should be called."""
        from shared.events.events import GCReapEvent
        from shared.event_handling.handler import dispatch_event

        evt = GCReapEvent(job_uuid=job_uuid, user_uuid=user_uuid, summary="reaped.")

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            await dispatch_event(evt)
            mock_redis.assert_called_once()
            # Verify stream key includes user/job uuid
            call_kwargs = mock_redis.call_args[1]
            assert call_kwargs.get("job_uuid") == job_uuid
            assert call_kwargs.get("user_uuid") == user_uuid

    @pytest.mark.asyncio
    async def test_error_event_propagates_and_logs(self, job_uuid, user_uuid):
        """ErrorEvent has both write_log and propagate_state True."""
        from shared.events.error_event import ErrorEvent
        from shared.errors.container_runtime_errors import ContainerNotFound
        from shared.event_handling.handler import dispatch_event

        err = ContainerNotFound()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        with patch(PATCH_LOGGER) as mock_logger, \
             patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            await dispatch_event(evt)
            mock_logger.assert_called_once()
            mock_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_raises_type_error_for_non_base_event(self):
        """Passing an object that is not a VireBaseEvent must raise TypeError."""
        from shared.event_handling.handler import dispatch_event

        with pytest.raises(TypeError):
            await dispatch_event("not an event")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_dispatch_raises_type_error_for_error_event_with_non_vire_error(
        self, job_uuid, user_uuid
    ):
        """ErrorEvent wrapping a plain Exception (not VireBaseError) must raise TypeError."""
        from shared.events.error_event import ErrorEvent
        from shared.event_handling.handler import dispatch_event

        # Manually bypass __post_init__ by supplying a non-VireBaseError error field
        evt = ErrorEvent.__new__(ErrorEvent)
        # Manually set slots to mimic an ErrorEvent with an invalid error type
        object.__setattr__(evt, "event", "Error Event")
        object.__setattr__(evt, "job_uuid", job_uuid)
        object.__setattr__(evt, "user_uuid", user_uuid)
        object.__setattr__(evt, "error", ValueError("not a VireBaseError"))
        object.__setattr__(evt, "diag_code", "VC-FAKE-001")
        object.__setattr__(evt, "summary", "fake")
        object.__setattr__(evt, "severity", "critical")
        object.__setattr__(evt, "write_log", True)
        object.__setattr__(evt, "propagate_state", True)
        object.__setattr__(evt, "timestamp", datetime.now(UTC))

        with pytest.raises(TypeError):
            await dispatch_event(evt)

    @pytest.mark.asyncio
    async def test_dispatch_with_job_details_included_in_user_report(
        self, job_uuid, user_uuid
    ):
        """
        When job_details is supplied to dispatch_event and propagate_state is True,
        the user report string sent to Redis should contain the job_details content.
        """
        from shared.events.error_event import ErrorEvent
        from shared.errors.container_runtime_errors import ContainerNotFound
        from shared.event_handling.handler import dispatch_event

        err = ContainerNotFound()
        evt = ErrorEvent(job_uuid=job_uuid, user_uuid=user_uuid, error=err)

        captured = {}

        async def fake_redis(line, *, job_uuid, user_uuid):
            captured["line"] = line

        with patch(PATCH_LOGGER), patch(PATCH_REDIS, side_effect=fake_redis):
            await dispatch_event(
                evt,
                job_details={"Branch": "feature/xyz", "Provider": "Github"},
            )

        assert "Branch: feature/xyz" in captured["line"]
        assert "Provider: Github" in captured["line"]


# ── state_propagation tests ───────────────────────────────────────────────────

class TestStatePropagation:
    """send_report should call publish_log_redis with a non-empty formatted report."""

    @pytest.mark.asyncio
    async def test_send_report_calls_redis_with_formatted_string(
        self, job_uuid, user_uuid
    ):
        from shared.event_handling.handler_context import EventHandlerContext
        from shared.event_handling.state_propagation import send_report

        ctx = EventHandlerContext(
            event="TestEvent",
            timestamp=datetime.now(UTC),
            diag_code="VC-TEST-001",
            severity="warn",
            summary="A problem occurred",
            job_uuid=job_uuid,
            user_uuid=user_uuid,
        )

        with patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            await send_report(ctx)
            mock_redis.assert_called_once()
            line_sent = mock_redis.call_args.kwargs["line"]
            assert isinstance(line_sent, str)
            assert len(line_sent) > 0

    @pytest.mark.asyncio
    async def test_propagate_state_delegates_to_send_report(
        self, job_uuid, user_uuid
    ):
        from shared.event_handling.handler_context import EventHandlerContext
        from shared.event_handling.state_propagation import propagate_state

        ctx = EventHandlerContext(
            event="GCReap",
            timestamp=datetime.now(UTC),
            diag_code="VC-GC-CONTAINER_REAPED",
            severity="warn",
            summary="Container was reaped.",
            job_uuid=job_uuid,
            user_uuid=user_uuid,
        )

        with patch(PATCH_REDIS, new_callable=AsyncMock) as mock_redis:
            await propagate_state(ctx)
            mock_redis.assert_called_once()


# ── error hierarchy / base_error tests ───────────────────────────────────────

class TestVireBaseError:
    """VireBaseError instances should be valid Python exceptions and carry metadata."""

    def test_base_error_is_exception(self):
        from shared.errors.base_error import VireBaseError

        err = VireBaseError(
            error_title="Something broke",
            error_code="VC-TEST-001",
            severity="critical",
        )
        assert isinstance(err, Exception)

    def test_base_error_message_is_title(self):
        from shared.errors.base_error import VireBaseError

        err = VireBaseError(
            error_title="Something broke",
            error_code="VC-TEST-001",
            severity="critical",
        )
        assert str(err) == "Something broke"

    def test_container_runtime_errors_inherit_base(self):
        from shared.errors.container_runtime_errors import (
            ContainerCreationFail,
            ContainerNotFound,
            ContainerAdapterAPIError,
            OutputDirNotFound,
        )
        from shared.errors.base_error import VireBaseError

        for klass in (ContainerCreationFail, ContainerNotFound, ContainerAdapterAPIError, OutputDirNotFound):
            assert issubclass(klass, VireBaseError)

    def test_scheduler_errors_inherit_base(self):
        from shared.errors.scheduler_errors import NoJobStateError
        from shared.errors.base_error import VireBaseError

        assert issubclass(NoJobStateError, VireBaseError)

    def test_validation_errors_inherit_base(self):
        from shared.errors.validation_errors import (
            InvalidPackageJsonError,
            InvalidVireTomlError,
            PackageManagerException,
            UnsupportedFrameworkError,
            InvalidOutDirError,
        )
        from shared.errors.base_error import VireBaseError

        for klass in (
            InvalidPackageJsonError,
            InvalidVireTomlError,
            PackageManagerException,
            UnsupportedFrameworkError,
            InvalidOutDirError,
        ):
            assert issubclass(klass, VireBaseError)

    def test_container_not_found_default_title(self):
        from shared.errors.container_runtime_errors import ContainerNotFound

        err = ContainerNotFound()
        assert err.error_title == "Container not found."
        assert err.error_code == "VC-IN-SANDBOX_NOT_FOUND"

    def test_no_job_state_error_default_fields(self):
        from shared.errors.scheduler_errors import NoJobStateError

        err = NoJobStateError()
        assert err.error_code == "VC-IN-NO_JOB_STATE"
        assert err.severity == "critical"
