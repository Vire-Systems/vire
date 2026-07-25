"""
The module resposible for formatting:
   1. errors into user log reports.
   2. Errors into internal logs.
"""

from collections.abc import Mapping, Sequence
from json import dumps
from shared.event_handling.handler_context import EventHandlerContext


def format_internal_log(
    context: EventHandlerContext, extra_details: dict[str, str]
) -> str:
    log_dict = {
        "event": context.event,
        "timestamp": str(context.timestamp),
        "diag_code": context.diag_code,
        "severity": context.severity,
        "summary": context.summary,
        "job_uuid": context.job_uuid,
    }
    log_dict.update(extra_details)
    return dumps(log_dict)


# User reports
def _format_report(
    heading: str,
    data: Mapping[str, str] | Sequence[str] | None,
) -> list[str]:
    """
    format data based on heading and data.
    """
    if not data:
        return []

    if isinstance(data, Mapping):
        return [
            heading + ":",
            *(f"    {key}: {value}" for key, value in data.items()),
        ]

    elif isinstance(data, Sequence):
        return [
            heading + ":",
            *(f"    - {item}" for item in data),
        ]


def format_user_report(context: EventHandlerContext) -> str:
    """
    Format EventHandlerContext into a user report.
    Refer to the documentation for the user report format.
    """
    report = [
        f"{context.severity.capitalize()}: {context.diag_code}",
        "",
        "Summary:",
        f"    {context.summary}",
        "",
    ]

    report.extend(
        _format_report(
            "Job Details",
            {
                "Job UUID": context.job_uuid,
                **(context.job_details or {}),
            },
        )
    )

    for heading, data in (
        ("Possible Causes", context.possible_causes),
        ("Possible Fixes", context.possible_fixes),
        ("Note", context.notes),
    ):
        section = _format_report(heading, data)
        if section:
            report.extend(["", *section])

    return "\n".join(report)
