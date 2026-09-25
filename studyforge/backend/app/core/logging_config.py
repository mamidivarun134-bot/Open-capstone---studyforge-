"""
Application-wide logging configuration.

Uses standard library logging with a consistent format so logs are
readable both locally and when aggregated by a hosting platform.
"""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        # Avoid duplicate handlers on reload.
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers.
    logging.getLogger("passlib").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
