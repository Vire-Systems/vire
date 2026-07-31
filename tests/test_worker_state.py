"""
Integration tests for BuildScheduler/worker/resolve_worker_state.py.

The worker state machine maintains its own synchronous SQLite connection
against the same shared DB file used by the scheduler.

Covers:
  - fetch_job_status — returns current status from BuildState
  - update_job_state — enforces the allowlist-based state transition rules
  - status_update_allowlist — the transition allowlist is correct
  - db_session context manager — rollback on exception, commit on success

These tests use a real temporary SQLite database (same schema as the scheduler)
to verify actual state transitions rather than mocking the DB layer.
"""

import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


# ── helpers / fixtures ────────────────────────────────────────────────────────

def make_db_with_schema(db_path: str) -> None:
    """Create the BuildState table used by the worker's SQLite queries."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS BuildState (
            job_uuid TEXT PRIMARY KEY,
            user_uuid TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            error TEXT
        )
    """)
    conn.commit()
    conn.close()


def seed_job(db_path: str, job_uuid: str, user_uuid: str, status: str) -> None:
    """Insert a job row directly via SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO BuildState (job_uuid, user_uuid, status) VALUES (?, ?, ?)",
        (job_uuid, user_uuid, status),
    )
    conn.commit()
    conn.close()


def fetch_raw_status(db_path: str, job_uuid: str) -> str | None:
    """Read status directly from the DB (outside any worker abstraction)."""
    conn = sqlite3.connect(db_path)
    result = conn.execute(
        "SELECT status FROM BuildState WHERE job_uuid=?", (job_uuid,)
    ).fetchone()
    conn.close()
    return result[0] if result else None


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite DB with the BuildState schema."""
    db_file = str(tmp_path / "test_worker.db")
    make_db_with_schema(db_file)
    return db_file


@pytest.fixture
def job_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def user_uuid():
    return str(uuid.uuid4())


# ── db_session context manager tests ─────────────────────────────────────────

class TestDbSession:
    """db_session should commit on success and rollback on exception."""

    def test_successful_write_is_committed(self, temp_db, job_uuid, user_uuid):
        from BuildScheduler.worker.resolve_worker_state import db_session

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db

            with db_session(temp_db) as conn:
                conn.execute(
                    "INSERT INTO BuildState (job_uuid, user_uuid, status) VALUES (?, ?, ?)",
                    (job_uuid, user_uuid, "queued"),
                )

        # After context exits normally, data should be committed
        status = fetch_raw_status(temp_db, job_uuid)
        assert status == "queued"

    def test_exception_causes_rollback(self, temp_db, job_uuid, user_uuid):
        from BuildScheduler.worker.resolve_worker_state import db_session

        # Seed a row so we can verify it is unchanged after rollback
        seed_job(temp_db, job_uuid, user_uuid, "queued")

        with pytest.raises(ValueError, match="intentional rollback"):
            with db_session(temp_db) as conn:
                conn.execute(
                    "UPDATE BuildState SET status=? WHERE job_uuid=?",
                    ("running", job_uuid),
                )
                raise ValueError("intentional rollback")

        # The update must have been rolled back
        status = fetch_raw_status(temp_db, job_uuid)
        assert status == "queued"


# ── fetch_job_status tests ────────────────────────────────────────────────────

class TestFetchJobStatus:
    """fetch_job_status queries the worker's DB file for a job's current status."""

    def test_returns_status_for_known_job(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.worker.resolve_worker_state import fetch_job_status

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            status = fetch_job_status(job_uuid=job_uuid, user_uuid=user_uuid)

        assert status == "running"

    def test_returns_queued_status(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "queued")

        from BuildScheduler.worker.resolve_worker_state import fetch_job_status

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            status = fetch_job_status(job_uuid=job_uuid, user_uuid=user_uuid)

        assert status == "queued"

    def test_returns_finished_status(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "finished")

        from BuildScheduler.worker.resolve_worker_state import fetch_job_status

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            status = fetch_job_status(job_uuid=job_uuid, user_uuid=user_uuid)

        assert status == "finished"


# ── update_job_state / allowlist tests ───────────────────────────────────────

class TestStatusUpdateAllowlist:
    """Verify the status_update_allowlist encodes the correct state machine."""

    def test_queued_can_transition_to_running(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert "running" in status_update_allowlist["queued"]

    def test_queued_can_transition_to_cancelled(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert "cancelled" in status_update_allowlist["queued"]

    def test_running_can_transition_to_finished(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert "finished" in status_update_allowlist["running"]

    def test_running_can_transition_to_crashed(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert "crashed" in status_update_allowlist["running"]

    def test_finished_cannot_transition(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert status_update_allowlist["finished"] == []

    def test_crashed_cannot_transition(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert status_update_allowlist["crashed"] == []

    def test_cancelled_cannot_transition(self):
        from BuildScheduler.worker.resolve_worker_state import status_update_allowlist
        assert status_update_allowlist["cancelled"] == []


class TestUpdateJobState:
    """update_job_state enforces allowlist-based transitions against the real DB."""

    def test_valid_transition_queued_to_running(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "queued")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="running", prev_status="queued")

        assert fetch_raw_status(temp_db, job_uuid) == "running"

    def test_valid_transition_running_to_finished(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="finished", prev_status="running")

        assert fetch_raw_status(temp_db, job_uuid) == "finished"

    def test_valid_transition_running_to_crashed(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="crashed", prev_status="running")

        assert fetch_raw_status(temp_db, job_uuid) == "crashed"

    def test_invalid_transition_finished_to_running_is_ignored(
        self, temp_db, job_uuid, user_uuid
    ):
        """update_job_state silently ignores disallowed transitions."""
        seed_job(temp_db, job_uuid, user_uuid, "finished")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="running", prev_status="finished")

        # Status must remain "finished"
        assert fetch_raw_status(temp_db, job_uuid) == "finished"

    def test_invalid_transition_crashed_to_cancelled_is_ignored(
        self, temp_db, job_uuid, user_uuid
    ):
        seed_job(temp_db, job_uuid, user_uuid, "crashed")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="cancelled", prev_status="crashed")

        assert fetch_raw_status(temp_db, job_uuid) == "crashed"

    def test_transition_requires_matching_prev_status_in_db(
        self, temp_db, job_uuid, user_uuid
    ):
        """
        The UPDATE uses a WHERE clause matching both job_uuid AND prev_status.
        If the actual DB status differs from prev_status, no row is updated.
        """
        # DB has "running" but we claim prev_status="queued"
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.worker.resolve_worker_state import update_job_state

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db
            update_job_state(job_uuid=job_uuid, status_msg="finished", prev_status="queued")

        # The DB status must remain "running" since WHERE job_uuid=? AND status="queued" matched nothing
        assert fetch_raw_status(temp_db, job_uuid) == "running"


# ── full worker state lifecycle ───────────────────────────────────────────────

class TestWorkerStateLifecycle:
    """
    Simulate the complete state transitions a worker process makes:
      queued → running → finished
    """

    def test_queued_to_running_to_finished(self, temp_db, job_uuid, user_uuid):
        from BuildScheduler.worker.resolve_worker_state import (
            fetch_job_status,
            update_job_state,
        )

        seed_job(temp_db, job_uuid, user_uuid, "queued")

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db

            # Worker starts up: queued → running
            current = fetch_job_status(job_uuid, user_uuid)
            assert current == "queued"
            update_job_state(job_uuid, status_msg="running", prev_status=current)

            # Mid-work
            current = fetch_job_status(job_uuid, user_uuid)
            assert current == "running"

            # Worker completes: running → finished
            update_job_state(job_uuid, status_msg="finished", prev_status=current)

        final_status = fetch_raw_status(temp_db, job_uuid)
        assert final_status == "finished"

    def test_queued_to_running_to_crashed(self, temp_db, job_uuid, user_uuid):
        from BuildScheduler.worker.resolve_worker_state import (
            fetch_job_status,
            update_job_state,
        )

        seed_job(temp_db, job_uuid, user_uuid, "queued")

        with patch("BuildScheduler.worker.resolve_worker_state.worker_config") as mock_cfg:
            mock_cfg.DB_FILE = temp_db

            current = fetch_job_status(job_uuid, user_uuid)
            update_job_state(job_uuid, status_msg="running", prev_status=current)

            current = fetch_job_status(job_uuid, user_uuid)
            update_job_state(job_uuid, status_msg="crashed", prev_status=current)

        final = fetch_raw_status(temp_db, job_uuid)
        assert final == "crashed"
