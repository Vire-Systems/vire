"""
Central module for all scheduler locks.

Locks:
-----
- task_removal_lock
"""
import asyncio
from collections import defaultdict

task_removal_lock = asyncio.Lock()
scheduler_lock = asyncio.Lock()
queue_insert_lock = asyncio.Lock()
job_status_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
