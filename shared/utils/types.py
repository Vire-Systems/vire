from typing import Literal, TypeAlias

Severity: TypeAlias = Literal[
    "info",
    "warn",
    "error",
    "critical",
    "exit"
]