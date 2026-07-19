

from shared.event_handling.formatter import format_user_report
from shared.event_handling.handler_context import EventHandlerContext
from shared.logging.pub_redis import publish_log_redis


async def send_report(context: EventHandlerContext)-> None:
    """
    Sends a report of the event to the end user via redis.
    """
    report_body = format_user_report(context)

    await publish_log_redis(
        line=report_body,
        job_uuid=context.job_uuid,
        user_uuid=context.user_uuid
    )

async def propagate_state(context: EventHandlerContext)-> None:
    """
    Top-level function handling propagation of data to external systems.

    External systems include:
    ---
        - The User
        - PostgreSQL
        - Redis
        And more in the future.
    """
    await send_report(context)