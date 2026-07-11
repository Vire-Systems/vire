"""
This module (worker_dataclasses) provides a dataclass called 'FrameworkAdapter'.

Consists -
1. FrameworkAdapter -
    image, output_dir, install_commands, build_commands
"""

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class FrameworkAdapter:
    """Dataclass for framework data."""
    image: str
    install_command: dict[str,str]
    build_command: dict[str,str]

@dataclass(frozen=True, slots=True)
class WorkerContext:
    """Context required for worker"""
    