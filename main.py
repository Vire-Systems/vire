import uvicorn
import logging
from dotenv import load_dotenv

load_dotenv("/home/vire/vire/.env")

from Vire.utils.state import logfile, log_value
from application import app
from BuildScheduler.shared.logging.logger_setup import setup_async_logging, stop_async_logging


logger = logging.getLogger(__name__)

if __name__=="__main__":
    try:
        setup_async_logging(logfile, log_value)
        uvicorn.run(app, host="127.0.0.1", port = 8000)
    finally:
        stop_async_logging()
