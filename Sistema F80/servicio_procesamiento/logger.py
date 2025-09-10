import logging
import logging.handlers
import os
import sys


def setup_worker_logging(name: str, log_dir="logs", log_to_console=False):
 
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    logger.propagate = False

    formatter = logging.Formatter(f'%(asctime)s - {name} - pid:%(process)d - %(levelname)s - %(message)s')

    info_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f'{name}.info.log'), maxBytes=10*1024*1024, backupCount=5
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(lambda record: record.levelno == logging.INFO)

    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, f'{name}.error.log'), maxBytes=10*1024*1024, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    logger.addHandler(info_handler)
    logger.addHandler(error_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
