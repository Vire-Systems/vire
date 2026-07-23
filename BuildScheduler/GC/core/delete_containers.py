import asyncio

from BuildScheduler.GC.core.gc_crud import get_user_uuid, update_job_status
from BuildScheduler.GC.utils.state import gc_config
from shared.errors.container_runtime_errors import ContainerAdapterAPIError, ContainerNotFound
from shared.container_runtimes.runtime_dc import RuntimeMetadata
from shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from shared.event_handling.handler import dispatch_event
from shared.events.events import GCReapEvent, LogEvent
from shared.shared_state import shared_config


async def remove_single_container(job_uuid: str) -> None:
    try:
        runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
        user_uuid = await get_user_uuid(job_uuid)
        assert user_uuid is not None
        await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)

        event = GCReapEvent(
            job_uuid = job_uuid, user_uuid=user_uuid,
            summary=f"Job terminated for excceding {gc_config.CONTAINER_REMOVAL_DELAY + 15}s limit."
        )

        await dispatch_event(event=event)

    # ignore since it could be the indication of scheduler unfreezing (if that's the cause of delayed removal)
    except ContainerNotFound:
        pass

    except ContainerAdapterAPIError as e:
        await dispatch_event(LogEvent(
            job_uuid=job_uuid,
            diag_code = "VC-IN-UNEXPECTED_INTERNAL_ERROR", severity="critical",
            internal_log="Unexpected error occured while deleting a container (Exception)",
            summary= e.error_title,
            exception_name=str(type(e).__name__), source = "gc"
        ))

    except Exception as e:
        await dispatch_event(LogEvent(
            job_uuid=job_uuid,
            diag_code = "VC-IN-UNEXPECTED_INTERNAL_ERROR", severity="critical",
            internal_log="Unexpected error occured while deleting a container (Exception)",
            summary= "[GC] Unable to remove container process. Unexpected Exception.",
            exception_name=str(type(e).__name__), source = "gc"
        ))


async def batch_remove() -> None:
    try:
        runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
        metadata = RuntimeMetadata(managed_by=shared_config.CONTAINER_METADATA["managed_by"], expires_at=None)
        expired_jobs = runtime.list_expired_containers(metadata=metadata)

        tasks: list[asyncio.Task[None]] = []
        async for job_uuid in expired_jobs:
            await update_job_status([job_uuid async for job_uuid in expired_jobs], error_code="VC-GC-001 ")
            tasks.append(asyncio.create_task(remove_single_container(job_uuid)))

        _ =await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        await dispatch_event(LogEvent(
            diag_code = "VC-IN-001", severity="critical",
            internal_log="Unable to collect. Unexpected error (Exception)",
            summary= "[GC] Unable to remove container process. Unexpected Exception.",
            exception_name=str(type(e).__name__), source = "gc"
        ))
