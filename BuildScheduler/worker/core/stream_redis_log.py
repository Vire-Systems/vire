from redis import from_url

from utils import state
from utils.vire_logger import cfn_log
from resolve_worker_state import fetch_job_status

assert state.redis_url is not None

r = from_url(state.redis_url)
client = state.client

# Helper called by 'stream_logs'
def publish_log_redis(line: str)-> None:
    try:
        assert state.job_uuid is not None
        assert state.user_uuid is not None

        job_status = fetch_job_status(job_uuid =state.job_uuid, user_uuid=state.user_uuid)

        if job_status == "cancelled":
            return

        data = {"payload": line}
        r.xadd(f"logs:{state.user_uuid}/{state.job_uuid}", data) # type: ignore[reportArgumentType]
    except Exception as e:
        cfn_log("critical", "[publish_log_redis] Unable to publish logs. Details: %s", e)


# Calls 'publish_log_redis'
def stream_logs(job_uuid: str)-> None:
    try:
        container = client.containers.get(job_uuid)
        for line in container.logs(stream=True, follow=True, stdout=True, stderr=True, timestamps=True):
            str_line = line.decode("utf-8")
            if len(str_line) >= 32:
                publish_log_redis(str_line)
    except Exception as e:
        cfn_log("critical", "[stream_logs] Error in stream_logs. Details: (%s)", e)
