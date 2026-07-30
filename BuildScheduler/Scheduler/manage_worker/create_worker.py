"""
This module (create_worker) is responsible for worker process creation.

Functions -
1. create_worker_process (async)
"""

import json
import subprocess

from BuildScheduler.Scheduler.db.sqlite_orm.crud import update
from BuildScheduler.Scheduler.manage_worker.del_container import delayed_delete
from BuildScheduler.Scheduler.utils.scheduler_dc import WorkerCreationParams
from BuildScheduler.Scheduler.utils.state import scheduler_config
from shared.errors.scheduler_errors import NoJobStateError
from shared.event_handling.handler import dispatch_event
from shared.events.events import LogEvent
from shared.state_transition import transition_job_state


# Helper
async def _wk_helper(WCP: WorkerCreationParams) -> None:
    try:
        # I def didn't forget to change paths after the refactor 😑 /s
        cmd_b = {
            "job_uuid": WCP.job_uuid,
            "user_uuid": WCP.user_uuid,
            "remote": WCP.remote_link,
            "repo_name": WCP.repo_name,
            "framework": WCP.framework,
            "pm": WCP.pm,
            "output_dir": WCP.output_dir,
            "install_req": WCP.install_req,
            "commit_id": WCP.commit_id,
        }
        argument = json.dumps(cmd_b)

        cmd = [
            "nohup",
            scheduler_config.PYTHON_BIN_PATH,
            "-m",
            scheduler_config.WORKER_PACKAGE_LOCATION,
            "--json_struct",
            argument,
        ]

        _ = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    except Exception:
        raise


async def create_worker_process(WCP: WorkerCreationParams) -> None:
    """
    An abstraction for worker process creation.

    Args-
        WCP - Worker creation params, abbrev. Params for this function.
    """

    try:
        async with transition_job_state(
            on_enter= None, on_exit = "running", on_error="crashed",
            state_updater = update.update_job_status,
            job_uuid = WCP.job_uuid
        ):
            _ = await _wk_helper(WCP)
            await delayed_delete(job_uuid=WCP.job_uuid, user_uuid=WCP.user_uuid)

    except NoJobStateError as e:
        await dispatch_event(
            event=LogEvent(
                user_uuid=WCP.user_uuid,
                job_uuid=WCP.job_uuid,
                diag_code=e.error_code,
                summary="Failed to create a sandbox for the job.",
                severity=e.severity,
                source="Scheduler",
                exception_name=type(e).__name__,
                internal_log=e.error_title,
            )
        )

    except Exception as e:
        await dispatch_event(
            event=LogEvent(
                user_uuid=WCP.user_uuid,
                job_uuid=WCP.job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                summary="Worker creation failed dueto an internal error.",
                source="scheduler",
                exception_name=type(e).__name__,
                internal_log="Worker creation failed for the container creation of the job.",
            )
        )
