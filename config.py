"""
MediTrack Configuration & Environment Provisions
Centralized configuration management for paths, thresholds, versioning, and logging.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Application Metadata
APP_NAME = "MediTrack"
APP_VERSION = "1.3.0"

# Directories & File Paths
APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
LOGS_DIR = os.path.join(APP_DATA_DIR, "logs")
DATABASE_FILE = os.path.join(APP_DATA_DIR, "meditrack.db")
LEGACY_DATABASE_FILE = "meditrack.db"
BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")
BACKUP_FILE = os.path.join(APP_DATA_DIR, "meditrack.pre-migration.bak")

# Clinical & Operational Thresholds
LOW_STOCK_THRESHOLD = 5         # Threshold in pills to trigger inventory warning
EXPIRY_WARNING_DAYS = 30        # Days before expiry to trigger alert
ALERT_WINDOW_MINUTES = 15       # Catch-up window for missed scheduled doses
WATCHER_INTERVAL_SECONDS = 30   # Polling frequency for the background watcher thread

def setup_logging():
    """
    Configures robust logging with dual outputs:
    1. Rotating log file in %APPDATA%/MediTrack/logs/meditrack.log (keeps up to 3 x 1MB backups)
    2. Standard console stream for development/debugging
    """
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, "meditrack.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s")
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)

        logger = logging.getLogger("MediTrack")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)
        return logger
    except Exception as e:
        # Fallback to standard console logger if AppData is read-only
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger("MediTrack")

logger = setup_logging()
