"""The module consisting of the scheduler loop function"""

import asyncio

from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job, get_worker_count
from BuildScheduler.Scheduler.db.sqlite_orm.crud import read
from BuildScheduler.Scheduler.utils.state import scheduler_config
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.logging.scheduler_logger import vire_logger


async def scheduler_loop():
    """The main scheduler loop that dispatches queued jobs."""
    vire_logger("info", "Scheduler loop starting up.")
    try:
        while True:
            worker_count = await get_worker_count()
            if not worker_count:
                raise ValueError
            available_slots = scheduler_config.MAX_BUILDS_NUMBER - worker_count
            await read.load_queued_builds(available_slots)
            _ = asyncio.create_task(dispatch_queued_job(available_slots))

            await asyncio.sleep(30)

    except Exception as e:
        await dispatch_event(LogEvent(
            diag_code = "VC-IN-UNEXPECTED_INTERNAL_ERROR", severity="critical",
            internal_log=str(e),
            summary= "[GC] Unable to remove container process. Unexpected Exception.",
            exception_name=str(type(e).__name__), source = "gc"
        ))
