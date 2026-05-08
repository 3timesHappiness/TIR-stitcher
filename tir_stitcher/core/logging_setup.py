"""Unified logging with rotating file handlers."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


PACKAGE_LOGGER_NAME = "tir_stitcher"


def setup_logging(
    log_dir: Path,
    project_name: str | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure dual logging: central log + optional per-project log + console."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger(PACKAGE_LOGGER_NAME)
    root.setLevel(level)

    # Avoid duplicate handlers on re-configuration
    if root.handlers:
        return root

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Central log
    central = RotatingFileHandler(
        log_dir / "pipeline.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    central.setLevel(level)
    central.setFormatter(fmt)
    root.addHandler(central)

    # Per-project log
    if project_name:
        proj = RotatingFileHandler(
            log_dir / f"{project_name}.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        proj.setLevel(level)
        proj.setFormatter(fmt)
        root.addHandler(proj)

    return root


def get_logger(name: str = "") -> logging.Logger:
    """Return a logger under the tir_stitcher namespace."""
    full = PACKAGE_LOGGER_NAME
    if name:
        full = f"{PACKAGE_LOGGER_NAME}.{name}"
    return logging.getLogger(full)


def log_banner(logger: logging.Logger, text: str) -> None:
    """Print a consistently-formatted section banner."""
    logger.info("=" * 60)
    logger.info(text)
    logger.info("=" * 60)
