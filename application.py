"""
The module used in main.py
This provides the fastapi app with the lifespan.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from BuildScheduler.Scheduler.db.sqlite_orm.models import init_db
from BuildScheduler.Scheduler.scheduler_loop import scheduler_loop
from shared.logging.pub_redis import r
from shared.logging.scheduler_logger import vire_logger
from shared.shared_state import shared_config
from Vire.api.routers import testrouter
from Vire.api.routers.build import build_req, cancel_build
from Vire.utils import async_requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan CM"""
    vire_logger("info", "[Vire core] start up.")
    tasks = []
    await init_db()
    tasks.append(asyncio.create_task(scheduler_loop()))
    try:
        yield
    finally:
        vire_logger("info", "[Vire Core] shutting down.")
        if not async_requests.client:
            vire_logger("info", "[async req setup] No client found. Ignoring aclose()...")
        else:
            await async_requests.client.aclose()
            vire_logger("info", "[async req setup] client pool closed.")
        await r.aclose()
        vire_logger("info", "[pub_redis] shared client closed.")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

routers = [testrouter.router, build_req.router, cancel_build.router]

for router in routers:
    app.include_router(router, prefix=f"/{shared_config.CORE_ID}/api/v1")


# Status
@app.get(f"/{shared_config.CORE_ID}/api/status")
async def api_status():
    return {"online": True}
