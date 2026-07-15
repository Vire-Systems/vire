"""The module consisting of the scheduler loop function"""

import asyncio

from BuildScheduler.Scheduler.core.dispatch_from_queue import dispatch_queued_job, get_worker_count
from BuildScheduler.Scheduler.db.sqlite_orm.crud import read
from BuildScheduler.Scheduler.utils.state import scheduler_config 
from BuildScheduler.shared.logging.scheduler_logger import vire_logger


async def scheduler_loop():
    """The main scheduler loop that dispatches queued jobs."""
    vire_logger("info", "Scheduler loop starting up.")
    try:
        while True:
            worker_count = await get_worker_count()
            available_slots = scheduler_config.MAX_BUILDS_NUMBER - worker_count
            await read.load_queued_builds(available_slots)
            _ = asyncio.create_task(dispatch_queued_job(available_slots))

            await asyncio.sleep(30)
    except ValueError:
        vire_logger("critical", "[scheduler_loop] The function get_worker_count returned a non int value.")
    except Exception as e:
        vire_logger("critical", "[scheduler_loop] Scheduler loop shutting down because of an error. Details: %s", str(e))
