import logging

import uvicorn
from dotenv import load_dotenv

_ = load_dotenv("/home/vire/vire/.env")

from application import app
from shared.logging.logger_setup import setup_async_logging, stop_async_logging
from Vire.utils.state import log_value, logfile

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        setup_async_logging(logfile, log_value)
        uvicorn.run(app, host="127.0.0.1", port=8000)
    finally:
        stop_async_logging()
