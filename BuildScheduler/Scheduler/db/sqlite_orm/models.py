"""
This module (models) is responsible foe providing the db schemas and the init function.

DB Schema classes -
    1.

Functions -
    1. init (async)
"""

from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, Integer, String, func
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

from BuildScheduler.Scheduler.db.sqlite_orm.db import Base, engine
from shared.logging.scheduler_logger import vire_logger


class BuildData(Base):
    """
    The DB schema class for Build request related data.

    Attributes -
        job_uuid: String,
        user_uuid: str,
        remote_link: str,
        commit_id: str,
        provider: str,
        remote_user: str,
        remote_reponame: str,
        branch: str
    """

    __tablename__: str = "BuildData"
    job_uuid: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    user_uuid: Mapped[str] = mapped_column(String, nullable=False)
    remote_link: Mapped[str] = mapped_column(String, nullable=False)
    commit_id: Mapped[str] = mapped_column(String, nullable=False)
    repo_name: Mapped[str] = mapped_column(String, nullable=False)
    framework: Mapped[str] = mapped_column(String, nullable=False)
    pm: Mapped[str] = mapped_column(String, nullable=False)
    install_req: Mapped[bool] = mapped_column(Boolean, nullable=False)
    output_dir: Mapped[str] = mapped_column(String, nullable=False)


class BuildState(Base):
    """
    Table for build states.

    This SQLAlchemy schema handles build states.
    Only running / queued builds should be present here.
    """

    __tablename__: str = "BuildState"
    job_uuid: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    user_uuid: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)
    error: Mapped[str] = mapped_column(String, nullable=True)


async def init_db(engine: AsyncEngine = engine):
    """Initialize the database and start sqlalchemy engine."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    vire_logger("info", "Vire state database has started up.")
