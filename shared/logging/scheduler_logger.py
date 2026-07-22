"""
Basic logging setup for vire scheduler.

Functions -
    1. vire_logger
"""

import logging
from typing import Literal

from typing_extensions import Callable

def vire_logger(
    log_type: Literal["info", "warn", "error", "critical", "exit"],
    obj:str, *args: str
)-> None:

    """Logging function for Scheduler (shared)"""
    logger = logging.getLogger()
    l_type = log_type.lower()

    std_logging_objects: dict[str, Callable[..., None]]  = {
        "info": logger.info,
        "warn": logger.warning,
        "exit": logger.critical
    }
    
    special_logging_objects: dict[str, Callable[..., None]] = {
        "error": logger.error,
        "critical": logger.critical
    }

    # Main logic
    try:
        if l_type in std_logging_objects.keys():
            std_logging_objects[l_type](obj, *args)

        elif l_type in special_logging_objects.keys():
            special_logging_objects[l_type](obj, *args, stack_info=True, exc_info=True)

        else:
            logger.warning("[cfn_log] Log type '%s' is not supported by cfn_log.", l_type)
    except Exception as e:
        logger.error("[cfn_log] An error occoured in the logging function. (%s)", e, exc_info=True)
