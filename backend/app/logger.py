import logging
import os
from logging.handlers import RotatingFileHandler

# Determine absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 5, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


scraper_logger = setup_logger("scraper", os.path.join(LOG_DIR, "scraper.log"))
server_logger = setup_logger("server", os.path.join(LOG_DIR, "server.log"))
