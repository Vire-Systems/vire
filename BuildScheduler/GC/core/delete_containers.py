import asyncio

from textwrap import dedent

from BuildScheduler.shared.container_runtimes.errors import ContainerNotFound
from BuildScheduler.shared.container_runtimes.runtime_dc import RuntimeMetadata
from BuildScheduler.shared.container_runtimes.runtime_registry import RUNTIME_REGISTRY
from BuildScheduler.shared.shared_state import shared_config
from BuildScheduler.GC.core.gc_crud import get_user_uuid, update_job_status
from BuildScheduler.shared.logging.scheduler_logger import vire_logger
from BuildScheduler.shared.logging.pub_redis import publish_log_redis


async def remove_single_container(job_uuid: str)-> None:
    try:
        runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
        user_uuid = await get_user_uuid(job_uuid)
        assert user_uuid is not None
        await asyncio.to_thread(runtime.remove, job_uuid=job_uuid)

        vire_logger("info","[GC remove_single_container] Terminated an overdue container process. Job UUID: '%s').", job_uuid)
        await publish_log_redis(line=dedent(
                f"""
                Error: VC-GC-001. Job terminated for excceding 315s limit.
            
                Details:
                    Job UUID: {job_uuid}
            
                Suggested fixes:
                    1. Check for unoptimized dependencies. Check for that by using 'webpack-bundle-analyzer'.
                    2. Use speed measure plugin (speed-measure-plugin) to find what the bottleneck is.
                """),
            user_uuid=user_uuid, job_uuid=job_uuid )

    # ignore since it could be the indication of scheduler unfreezing (if that's the cause of delayed removal)
    except ContainerNotFound:
        pass

    except Exception:
        vire_logger("critical", "[GC remove_single_container] Unable to remove container process '%s'.", job_uuid)

async def batch_remove()-> None:
    try:
        runtime = RUNTIME_REGISTRY[shared_config.CONTAINER_RUNTIME]()
        metadata = RuntimeMetadata(
            managed_by= shared_config.CONTAINER_METADATA["managed_by"],
            expires_at = None
        )
        expired_jobs = runtime.list_expired_containers(metadata=metadata)

        tasks = []
        async for job_uuid in expired_jobs:
            await update_job_status([job_uuid async for job_uuid in expired_jobs], error_code = "VC-GC-001 ")
            tasks.append(
                asyncio.create_task(remove_single_container(job_uuid))
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        vire_logger("critical","[GC batch_remove] Batch remove raised an exception. Details: %s", e)
