"""The main gc.py entrypoint."""

import asyncio
import logging
import os

from dotenv import load_dotenv

_ = load_dotenv("/home/vire/vire/.env")

from BuildScheduler.GC.core.delete_containers import batch_remove
from BuildScheduler.GC.utils.state import gc_config
from shared.logging.logger_setup import setup_async_logging, stop_async_logging
from shared.logging.pub_redis import r

from shared.events.events import LogEvent
from shared.event_handling.handler import dispatch_event

logger = logging.getLogger(__name__)
logfile_location = os.path.join(gc_config.LOGFILE_DIR, "gc.log")


async def gc_loop_iteration():
    """
    A single iteration of the GC loop.
    This is intended to be called repeatedly.
    """
    try:
        await batch_remove()

    except Exception as e:
        await dispatch_event(
            event=LogEvent(
                diag_code="VC-IN-001",
                severity="critical",
                internal_log="Unexpected error (Exception) when starting the GC loop.",
                summary="[GC] Unable to collect timed out builds.",
                exception_name=type(e).__name__,
                source="gc",
            )
        )


async def gc_core_loop():
    """The asynchronous core GC loop."""
    try:
        while True:
            await gc_loop_iteration()
            await asyncio.sleep(30)

    finally:
        await r.aclose()


if __name__ == "__main__":
    try:
        setup_async_logging(log_file=logfile_location, log_level=gc_config.LOG_LEVEL)
        asyncio.run(gc_core_loop())
    except KeyboardInterrupt:
        exit(0)
    finally:
        stop_async_logging()
