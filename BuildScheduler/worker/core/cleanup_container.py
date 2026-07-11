"""
This module (cleanup_container) handles container removal.

Functions -
1. remove_container (sync)

"""

from textwrap import dedent

from core.stream_redis_log import publish_log_redis
from resolve_worker_state import update_job_state
from schema.base_runtime import ContainerRuntime
from utils import state
from utils.vire_logger import cfn_log

def remove_container(job_uuid: str):
    """Name (UUID4 used for naming) based container remover"""
    container_runtime = state.container_runtime
    assert container_runtime is not None
    from utils.container_runtimes.runtime_registry import RUNTIME_REGISTRY
    try:
        runtime: ContainerRuntime = RUNTIME_REGISTRY[container_runtime]()
        runtime.remove(job_uuid)

    except KeyError:
        cfn_log("critical", "The container runtime class for '%s' doesn't exist. VC-VD-00", container_runtime)
        publish_log_redis(dedent(
            """
            Error: VC-WK-001. Vire faced an unexpected issue while trying to create a worker process.

            If you see this error, Please create an issue on github with a screenshot. This is an internal error.

            Cause: Configuration error
            """
        )) 
        update_job_state(
            job_uuid= job_uuid,
            status= "finished",
            prev_status="running"
        )

    except Exception:
        raise
