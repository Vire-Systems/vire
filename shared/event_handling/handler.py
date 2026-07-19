from shared.event_handling.formatter import format_internal_log
from shared.event_handling.handler_context import EventHandlerContext
from shared.errors.base_error import VireBaseError
from shared.event_handling.state_propagation import propagate_state
from shared.events.base_event import VireBaseEvent
from shared.events.error_event import ErrorEvent
from shared.logging.scheduler_logger import vire_logger


# (Comment for self) This needs to:

# log after checking whether event.write_logs is true or not
# propagate after checking whether event.propagate_state is true or not
# job, user uuid for redis stream


# Helper, creates handler context.
def get_context(event: VireBaseEvent, job_details: dict[str, str] | None)-> EventHandlerContext:
    """
    Return an instance of EventHandlerContext populated with appropriate details.
    """
    return EventHandlerContext(
        event = event.event,
        timestamp = event.timestamp,
        diag_code= event.diag_code,
        severity= event.severity,
        job_uuid= event.job_uuid,
        user_uuid= event.user_uuid,
        summary= event.summary,
        job_details = job_details,
        **event.get_extra_content(),
    )

async def dispatch_event(
    event: VireBaseEvent,
    *,
    job_details: dict[str, str] | None = None,
)-> None:
    """
    Handle all Vire-specific events.

    Parameters
    ----------
    event:
        The Vire Event to handle.

    job_details:
        Optional additional details that can be added to the user report.

    # Note: The Key:Value pair in job_details should be user presentable. ie; 
        - "Package Manager":"npm"
        - "Branch":"main"
        Will be formatted to '`Branch: main`' in the user report.
    """

    if not isinstance(event, VireBaseEvent):
        raise TypeError(f"{type(event ).__name__} must inherit from VireBaseEvent.")

    if isinstance(event, ErrorEvent):
        if not isinstance(event.error, VireBaseError):
            raise TypeError(
                f"The Error Event's error attribute ({type(event.error).__name__}) must inherit from VireBaseError."
            )

    context = get_context(event=event, job_details=job_details)

    if event.write_log:
        log_body: str = format_internal_log(context=context, extra_details=event.get_log_extras())
        vire_logger(event.severity, log_body)

    if event.propagate_state:
        await propagate_state(context)
