"""
The main gc.py entrypoint.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv("/home/vire/vire/.env")

from BuildScheduler.GC.core.delete_containers import batch_remove
from BuildScheduler.shared.logging.logger_setup import setup_async_logging, stop_async_logging
from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from BuildScheduler.GC.utils.state import gc_config
from BuildScheduler.shared.logging.pub_redis import r

logger = logging.getLogger(__name__)
logfile_location = os.path.join(gc_config.LOGFILE_DIR, "gc.log")

async def gc_core_loop():
    """The core GC loop. Asynchronous."""
    try:
        while True:
            try:
                await batch_remove()
    
            except Exception as e:
                vire_logger("critical", "[GC gc_core_loop] Unable to collect. Details: %s", e)

            await asyncio.sleep(30)

    finally:
        await r.aclose()


if __name__ == "__main__":
    try:
        setup_async_logging(log_file=logfile_location, log_level=gc_config.LOG_LEVEL)
        vire_logger("info", "GC starting.")
        asyncio.run(gc_core_loop())
    except KeyboardInterrupt:
        vire_logger("info", "[GC] Received KeyboardIntterupt. Exiting...")
    except Exception as e:
        vire_logger("critical", "[GC entry point] Unable to run GC loop. Details: %s", e)
    finally:
        stop_async_logging()
