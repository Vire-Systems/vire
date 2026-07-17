"""
The module resposible for formatting:
   1. errors into user log reports.
   2. Errors into internal logs.
"""

from typing import Mapping, Sequence
from shared.error_handling.handler_context import ErrorHandlerContext


# User reports
def _format_mapping(
    heading: str,
    data: Mapping[str, str] | None,
) -> list[str]:
    if not data:
        return []

    return [
        heading + ":",
        *(f"    {key}: {value}" for key, value in data.items()),
    ]


def _format_sequence(
    heading: str,
    data: Sequence[str] | None,
) -> list[str]:
    if not data:
        return []

    return [
        heading + ":",
        *(f"    - {item}" for item in data),
    ]


def format_user_report(context: ErrorHandlerContext) -> str:
    """
    Format -
    ---------
    '''
    ```
    Error Code: <...>
    
    Summary: 
        <...>
    
    Job Details:
        - <...>
    
    Possible Causes:
        - <...>
    
    Possible Fixes:
        - <...>
    
    Note:
        - <...>
    ```
    '''
    """

    report = [
        f"Error Code: {context.error_code}",
        "",
        "Summary:",
        f"    {context.error_title}",
        "",
    ]

    report.extend(
        _format_mapping(
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
        section = _format_sequence(heading, data)
        if section:
            report.extend(["", *section])

    return "\n".join(report)

