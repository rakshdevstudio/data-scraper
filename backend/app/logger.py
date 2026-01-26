import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("backend/logs", exist_ok=True)


def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 5, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


scraper_logger = setup_logger("scraper", "backend/logs/scraper.log")
server_logger = setup_logger("server", "backend/logs/server.log")
