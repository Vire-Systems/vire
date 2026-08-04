"""
Central module for all queues used in vire.
"""

import asyncio

db_build_queue: asyncio.Queue[str] = asyncio.Queue()
