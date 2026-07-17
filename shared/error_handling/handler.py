from shared.error_handling.handler_context import ErrorHandlerContext
from shared.errors.base_error import VireBaseError
from shared.logging.pub_redis import publish_log_redis
from shared.logging.scheduler_logger import vire_logger

from shared.error_handling.formatter import format_user_report


async def handle_vire_error(
    exc: VireBaseError,
    user_uuid: str,
    job_uuid: str, 
    update_state: bool,
    job_details: dict | None = None,
)-> None:
    """
    Handle all Vire-specific errors.

    Parameters
    ----------
    exc:
        The Vire exception to handle.

    job_uuid
    
    update_state:
        whether to update state to all integrations(postgres, ... etc.)

    job_details:
        the details to be added to the user report.
    

    context:
        A valid Vire context dataclass for the caller's domain.

        This is intentionally typed as `Any` because Python's type
        system cannot conveniently express "any Vire context dataclass"
        without forcing an unnecessary inheritance hierarchy.

    logging_function:
        Logger used to publish the formatted error report.
    """

    if not isinstance(exc, VireBaseError):
        raise ValueError(f"The exception class provided '{type(exc).__name__}' does not inherit from VireBaseError")
    
    formatter_context = ErrorHandlerContext(
        error_code = exc.error_code,
        error_title = exc.error_title,
        job_uuid = job_uuid,
        possible_causes = exc.possible_causes,
        possible_fixes = exc.possible_fixes,
        notes = exc.notes,
        job_details = job_details
    )

    internal_log = "%s: %s. Job UUID: %s"

    vire_logger(
        exc.severity,
        internal_log,

        exc.error_code,
        exc.error_title,
        job_uuid
    )

    user_report = format_user_report(context=formatter_context) + '\n'

    await publish_log_redis(line=user_report, user_uuid=user_uuid, job_uuid=job_uuid)

    if update_state:
        """
        TODO: implement Postgres stuff here. Maybe use an ORM or a shared function that does it
        """
    
