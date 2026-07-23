import sqlite3
from contextlib import contextmanager
from typing import Literal

from BuildScheduler.worker.utils.state import worker_config

status_update_allowlist: dict[str, list[str]] = {
    "queued": ["running", "crashed", "finished", "cancelled"],
    "running": ["crashed", "finished", "cancelled"],
    "crashed": [],
    "finished": [],
    "cancelled": [],
}


@contextmanager
def db_session(db_name: str):
    connection = sqlite3.connect(db_name)
    try:
        cursor = connection.cursor()

        _ = cursor.execute("PRAGMA journal_mode=WAL")
        _ = cursor.execute("PRAGMA busy_timeout=5000")

        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_job_status(job_uuid: str, user_uuid: str) -> str:
    with db_session(worker_config.DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
            SELECT status FROM BuildState
            WHERE job_uuid=? AND user_uuid=?
            """
        result: tuple[str] = cursor.execute(query, (job_uuid, user_uuid)).fetchone() # pyright: ignore[reportAny]
        return result[0]

def update_job_state(
    job_uuid: str,
    status: Literal["queued", "running", "crashed", "finished", "cancelled"],
    prev_status: Literal["queued", "running", "crashed", "finished", "cancelled"],
) -> None:
    allowed_updates: list[str] = status_update_allowlist[prev_status]

    if status not in allowed_updates:
        return

    with db_session(worker_config.DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
            UPDATE BuildState
            SET status=?
            WHERE
            job_uuid=? AND status=?
            """
        _ = cursor.execute(query, (status, job_uuid, prev_status))
