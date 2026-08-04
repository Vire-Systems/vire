"""
This module provides all of the CRUD operations the GC needs to function properly.
"""

import aiosqlite
from BuildScheduler.GC.utils.state import gc_config


async def get_user_uuid(job_uuid: str) -> str | None:
    """
    Returns the User UUID registered with the provided Job UUID from the DB.
    """
    async with aiosqlite.connect(gc_config.DB_PATH) as db:
        query = "SELECT user_uuid FROM BuildState WHERE job_uuid=?"
        _ = await db.execute("PRAGMA journal_mode=WAL")
        _ = await db.execute("PRAGMA busy_timeout=5000")
        cursor = await db.execute(query, (job_uuid,))

        user_uuid = await cursor.fetchone()
        if user_uuid is None:
            return None
        return user_uuid[0]


async def update_job_status(
    job_uuids: list[str], status: str = "terminated", error_code: str | None = None
) -> None:
    """
    Update the status of the jobs provided.

    Args:
    -----

    - job_uuids: A list of job UUIDs to mark as `<status_msg>`.
    - status: The status message (default is `'terminated'`)
    - error_code: The optional error code to be used to mark the reason of termination.
    """
    async with aiosqlite.connect(gc_config.DB_PATH) as db:
        placeholders = ",".join("?" for _ in job_uuids)

        # Pragmas
        _ = await db.execute("PRAGMA journal_mode=WAL")
        _ = await db.execute("PRAGMA busy_timeout=5000")

        # Main logic
        if error_code is None:
            query = f"UPDATE BuildState SET status=? WHERE job_uuid IN ({placeholders})"
            _ = await db.execute(query, (status, *job_uuids))
        else:
            query = f"UPDATE BuildState SET status=?, error=? WHERE job_uuid IN ({placeholders})"
            _ = await db.execute(query, (status, error_code, *job_uuids))

        await db.commit()
