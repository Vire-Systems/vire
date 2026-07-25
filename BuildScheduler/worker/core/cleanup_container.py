"""
This module (cleanup_container) handles container removal.

Functions -
1. remove_container (async)

"""

from BuildScheduler.worker.resolve_worker_state import update_job_state
from BuildScheduler.worker.schema.worker_dataclasses import WorkerContext
from BuildScheduler.worker.utils.state import worker_config

from shared.errors.container_runtime_errors import (
    ContainerAdapterAPIError,
    ContainerNotFound,
)
from shared.events.events import LogEvent
from shared.event_handling.handler import dispatch_event

from shared.container_runtimes.base_runtime import ContainerRuntime
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY


async def remove_container(worker_context: WorkerContext):
    """Name (UUID4 used for naming) based container remover"""
    try:
        runtime: ContainerRuntime = RUNTIME_REGISTRY[worker_config.CONTAINER_RUNTIME]()
        runtime.remove(worker_context.job_uuid)

    except (ContainerAdapterAPIError, ContainerNotFound) as e:
        await dispatch_event(
            LogEvent(
                job_uuid=worker_context.job_uuid,
                diag_code="VC-IN-UNEXPECTED_INTERNAL_ERROR",
                severity="critical",
                internal_log="Unexpected error occured while deleting a container (Exception)",
                summary=e.error_title,
                exception_name=str(type(e).__name__),
                source="gc",
            )
        )

    except KeyError as e:
        await dispatch_event(
            event=LogEvent(
                job_uuid=worker_context.job_uuid,
                user_uuid=worker_context.job_uuid,
                diag_code="VC-IN-001",
                source="worker",
                severity="critical",
                summary="Vire faced an unexpected issue while trying to create a worker process.",
                internal_log=f"The container runtime class for '{worker_config.CONTAINER_RUNTIME}' doesn't exist",
                exception_name=type(e).__name__,
                propagate_state=True,
            )
        )

    except Exception:
        raise

    finally:
        update_job_state(
            job_uuid=worker_context.job_uuid, status="finished", prev_status="running"
        )
