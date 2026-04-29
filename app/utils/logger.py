"""
Logging configuration for ForeksTrader.
"""
import logging
import sys

# Create logger
logger = logging.getLogger("foreks")
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Format
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File handler
try:
    file_handler = logging.FileHandler("foreks.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except Exception:
    pass
