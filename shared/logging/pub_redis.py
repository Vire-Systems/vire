import logging

import redis.asyncio as redis
from Vire.utils import state

assert state.redis_url is not None

r = redis.Redis.from_url(state.redis_url)

async def publish_log_redis(line: str, user_uuid: str ,job_uuid: str)-> None:
    try:
        stream = f"logs:{user_uuid}/{job_uuid}"
        data = {"payload": line}
        await r.xadd(stream, data, maxlen=1000, approximate=True) # type: ignore[reportArgumentType]
    except Exception as e:
        logging.critical("pub_redis failed. Details: %s", e, exc_info=True, stack_info=True)
