"""
This module (logger_setup.py) handles setting up an async QueueHandler and QueueListener to make logging calls async.
The logging calls are pushed into a queue and the thread reads and writes to file.

Functions -
    1. setup_async_logging
    2. stop_async_logging
"""

import logging
import queue
from logging.handlers import QueueHandler, QueueListener

Listener = None


def setup_async_logging(log_file: str, log_level: int = logging.INFO):
    """A logging setup using logging module's built in QueueHandler and QueueListener."""
    global listener

    file_handler = logging.FileHandler(log_file, encoding="utf-8")

    formatter = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(module)s : %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler.setFormatter(formatter)
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(QueueHandler(log_queue))

    Listener = QueueListener(log_queue, file_handler, respect_handler_level=True)
    Listener.start()


def stop_async_logging():
    """Stops async logging."""
    global Listener
    if Listener:
        Listener.stop()
