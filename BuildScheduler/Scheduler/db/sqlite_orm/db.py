"""The aiosqlite+sqlalchemy db initialization module."""

import os

from aiosqlite.cursor import Cursor
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event

from BuildScheduler.Scheduler.utils.state import scheduler_config

os.makedirs(os.path.dirname(scheduler_config.SQLITE_DB_PATH), exist_ok=True)

engine = create_async_engine(scheduler_config.DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

@event.listens_for(engine.sync_engine, "connect")
def sqlite_conn_setup(db_api_connection, connection_record)-> None:
    cursor: Cursor = db_api_connection.cursor()

    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
