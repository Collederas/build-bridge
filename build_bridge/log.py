import logging
import logging.handlers
import os
import sys
from PyQt6.QtCore import QStandardPaths, QCoreApplication
from PyQt6.QtWidgets import QMessageBox 


def setup_logging():
    QCoreApplication.setOrganizationName("Dr. Collederas")
    QCoreApplication.setApplicationName("Build Bridge")

    log_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)

    if not log_dir:
       log_dir = os.path.join(os.path.expanduser("~"), ".buildbridge", "logs")

    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            log_dir = "." # Log to current dir as last resort

    log_file = os.path.join(log_dir, "app.log")

    log_level = logging.INFO

    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    formatter = logging.Formatter(log_format)

    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8'
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("--- Application Started ---")
    logging.info(f"Logging initialized. Log file: {log_file}")
    logging.info(f"Log directory: {log_dir}")

    return log_dir