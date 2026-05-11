"""Unified logging with rotating file handlers + terminal ProgressReporter."""

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


PACKAGE_LOGGER_NAME = "tir_stitcher"


class ProgressReporter:
    """Writes progress and stage info to terminal, independent of file logging.

    Terminal shows: stage banners, progress percentages/ETA (via \\r overwriting).
    File logging handles all detailed log messages separately.
    """

    def __init__(self) -> None:
        self._start = 0.0
        self._last_len = 0

    def start_timer(self) -> None:
        self._start = time.time()

    def report(self, idx: int, total: int, extra: str = "") -> None:
        """Update progress line in terminal with \\r carriage return."""
        if total < 10 or idx % max(1, total // 10) == 0 or idx >= total:
            elapsed = time.time() - self._start
            rate = idx / max(elapsed, 0.1)
            eta = (total - idx) / max(rate, 0.001)
            pct = 100.0 * idx / total
            msg = f"  [{idx}/{total}] {pct:.0f}% | {elapsed:.0f}s elapsed | ~{eta:.0f}s remaining"
            if extra:
                msg += f" | {extra}"
            padded = msg + " " * max(0, self._last_len - len(msg))
            sys.stdout.write("\r" + padded)
            sys.stdout.flush()
            self._last_len = len(msg)
            if idx >= total:
                sys.stdout.write("\n")

    def info(self, msg: str, *args: object) -> None:
        """Write an info line to terminal, clearing current progress first."""
        if args:
            msg = msg % args
        if self._last_len > 0:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()


# Module-level singleton — imported by stages and pipeline
progress_reporter = ProgressReporter()


def setup_logging(
    log_dir: Path,
    project_name: str | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure logging: detailed logs to files, only WARNING+ to console.

    Terminal progress display is handled separately by ProgressReporter.
    """
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

    # Console handler — quiet by default, only WARNING+ in terminal
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Central log — everything at file level
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
