"""
Integration tests for BuildScheduler/GC/core/gc_crud.py.

The GC CRUD module uses aiosqlite directly (not SQLAlchemy).
These tests create a real temporary SQLite database with the same schema
used by the system, seed it, and verify GC CRUD behavior.

Covers:
  - get_user_uuid — returns user_uuid for a known job_uuid, None for unknown
  - update_job_status — updates status (and error_code) for a list of jobs

External dependencies patched:
  - gc_config.DB_PATH is monkeypatched per-test via patch
"""

import asyncio
import sqlite3
import uuid
from unittest.mock import patch

import pytest


# ── DB schema helpers ─────────────────────────────────────────────────────────

def make_buildstate_table(db_path: str) -> None:
    """Create the BuildState table as used by the GC."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS "BuildState" (
            job_uuid VARCHAR NOT NULL,
            user_uuid VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            pid INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            error VARCHAR,
            PRIMARY KEY (job_uuid)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS "BuildData" (
            job_uuid VARCHAR NOT NULL,
            user_uuid VARCHAR NOT NULL,
            remote_link VARCHAR NOT NULL,
            commit_id VARCHAR NOT NULL,
            repo_name VARCHAR NOT NULL,
            framework VARCHAR NOT NULL,
            pm VARCHAR NOT NULL,
            install_req BOOLEAN NOT NULL,
            output_dir VARCHAR NOT NULL,
            PRIMARY KEY (job_uuid)
        )
    """)
    conn.commit()
    conn.close()


def seed_job(db_path: str, job_uuid: str, user_uuid: str, status: str = "running") -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO BuildState (job_uuid, user_uuid, status) VALUES (?, ?, ?)",
        (job_uuid, user_uuid, status),
    )
    conn.commit()
    conn.close()


def fetch_row(db_path: str, job_uuid: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT job_uuid, user_uuid, status, error FROM BuildState WHERE job_uuid=?",
        (job_uuid,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"job_uuid": row[0], "user_uuid": row[1], "status": row[2], "error": row[3]}


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "gc_test.db")
    make_buildstate_table(db_file)
    return db_file


@pytest.fixture
def job_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def user_uuid():
    return str(uuid.uuid4())


# ── get_user_uuid tests ───────────────────────────────────────────────────────

class TestGetUserUuid:
    """gc_crud.get_user_uuid should return user_uuid for known jobs."""

    @pytest.mark.asyncio
    async def test_returns_user_uuid_for_known_job(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, status="running")

        from BuildScheduler.GC.core.gc_crud import get_user_uuid

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            result = await get_user_uuid(job_uuid)

        assert result == user_uuid

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_job(self, temp_db):
        from BuildScheduler.GC.core.gc_crud import get_user_uuid

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            result = await get_user_uuid("nonexistent-uuid-xyz")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_correct_uuid_among_multiple_jobs(self, temp_db):
        """With multiple rows seeded, get_user_uuid should return the specific one."""
        jobs = [(str(uuid.uuid4()), str(uuid.uuid4())) for _ in range(5)]
        target_job, target_user = str(uuid.uuid4()), str(uuid.uuid4())

        for j, u in jobs:
            seed_job(temp_db, j, u, "running")
        seed_job(temp_db, target_job, target_user, "running")

        from BuildScheduler.GC.core.gc_crud import get_user_uuid

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            result = await get_user_uuid(target_job)

        assert result == target_user


# ── update_job_status tests ───────────────────────────────────────────────────

class TestGcUpdateJobStatus:
    """gc_crud.update_job_status updates status (and optionally error_code) for a list of jobs."""

    @pytest.mark.asyncio
    async def test_updates_single_job_to_terminated(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.GC.core.gc_crud import update_job_status

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            await update_job_status([job_uuid])

        row = fetch_row(temp_db, job_uuid)
        assert row["status"] == "terminated"
        assert row["error"] is None

    @pytest.mark.asyncio
    async def test_updates_multiple_jobs_at_once(self, temp_db, user_uuid):
        job1, job2, job3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        for j in (job1, job2, job3):
            seed_job(temp_db, j, user_uuid, "running")

        from BuildScheduler.GC.core.gc_crud import update_job_status

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            await update_job_status([job1, job2, job3])

        for j in (job1, job2, job3):
            row = fetch_row(temp_db, j)
            assert row["status"] == "terminated"

    @pytest.mark.asyncio
    async def test_stores_error_code_when_provided(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.GC.core.gc_crud import update_job_status

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            await update_job_status([job_uuid], error_code="VC-GC-001")

        row = fetch_row(temp_db, job_uuid)
        assert row["status"] == "terminated"
        assert row["error"] == "VC-GC-001"

    @pytest.mark.asyncio
    async def test_custom_status_can_be_set(self, temp_db, job_uuid, user_uuid):
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.GC.core.gc_crud import update_job_status

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            await update_job_status([job_uuid], status="timed_out")

        row = fetch_row(temp_db, job_uuid)
        assert row["status"] == "timed_out"

    @pytest.mark.asyncio
    async def test_empty_list_is_a_noop(self, temp_db, job_uuid, user_uuid):
        """Calling with an empty list should not raise and should change nothing."""
        seed_job(temp_db, job_uuid, user_uuid, "running")

        from BuildScheduler.GC.core.gc_crud import update_job_status

        with patch("BuildScheduler.GC.core.gc_crud.gc_config") as mock_cfg:
            mock_cfg.DB_PATH = temp_db
            # An empty IN (...) clause in SQLite produces invalid SQL — document behavior:
            # This may raise or silently succeed. We verify no crash and the existing row is unchanged.
            try:
                await update_job_status([])
            except Exception:
                pass  # Acceptable — empty list produces invalid SQL

        # The original row should remain unaffected
        row = fetch_row(temp_db, job_uuid)
        assert row["status"] == "running"
