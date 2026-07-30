from contextlib import asynccontextmanager
from collections.abc import Awaitable, AsyncGenerator
from typing import Callable, TypeAlias, Literal
from inspect import iscoroutine

from shared.errors.base_error import VireBaseError

State: TypeAlias = Literal[
    "queued", "running", "crashed", "finished", "cancelled", "failed", "timed_out"
]

@asynccontextmanager
async def transition_job_state(
    on_enter: State | None,
    on_exit: State | None,
    on_error: State | None,
    state_updater: Callable[..., Awaitable[None] | None],
    **updater_args: str | int,
) -> AsyncGenerator[None, None]:
    """
    An Asynchronous Context Manager that handles state transitions in the SQLite DB
    which is used as a queue by the Scheduler.

    Args:
    -----
    - on_enter: Set when entering the CM.
    - on_exit: Set when CM exits without any exceptions.
    - on_error: Set when CM exits with an exception.

    - state_updater: The function (async or sync) used for updating the SQLite DB.
    - updater_args: The optional argument to pass into '`state_updater`'.
    """

    async def _apply_state(status_msg: State, **updater_args: str | int)-> None:
        """
        A Helper that does the boring task of checking stuff.
        """
        result = state_updater(status_msg = status_msg, **updater_args)
        if iscoroutine(result):
            await result


    if on_enter is not None:
        await _apply_state(status_msg= on_enter, **updater_args)

    try:
        yield

    except Exception as e:
        if on_error is None:
            raise

        error_code = e.error_code if isinstance(e, VireBaseError) else "UNEXPECTED_INTERNAL_ERROR"
        await _apply_state(on_error, error_code=error_code, **updater_args)
        raise

    else:
        if on_exit is None:
            return
        await _apply_state(on_exit, **updater_args)
