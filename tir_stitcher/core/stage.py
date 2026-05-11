"""Abstract base class for pipeline stages."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.logging_setup import progress_reporter
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import is_stage_done, mark_stage_done


class Stage(ABC):
    """Base class for a pipeline stage with skip/resume and dry-run support."""

    name: str = ""
    description: str = ""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logging.getLogger(f"tir_stitcher.stages.{self.name}")
        self._progress_start: float = 0.0

    def _progress_start_timer(self) -> None:
        self._progress_start = time.time()
        progress_reporter.start_timer()

    def _progress_log(self, idx: int, total: int, extra: str = "") -> None:
        """Update progress on terminal and log to file."""
        # Terminal: overwriting progress line
        progress_reporter.report(idx, total, extra)
        # Log file: plain text for record
        if self._progress_start:
            elapsed = time.time() - self._progress_start
            rate = idx / max(elapsed, 0.1)
            eta = (total - idx) / max(rate, 0.001)
            pct = 100.0 * idx / total
            msg = f"  [{idx}/{total}] {pct:.0f}% | {elapsed:.0f}s elapsed | ~{eta:.0f}s remaining"
            if extra:
                msg += f" | {extra}"
            self.logger.info(msg)

    def run(self, project: ProjectInfo, step: int = 0, total: int = 0) -> StageResult:
        """Public entry point: check skip, run, write stamp, return result."""

        banner = f"[{step}/{total}] {self.name}: {project.name}" if total else f"{self.name}: {project.name}"
        sep = "=" * 60

        # Terminal output via progress reporter
        progress_reporter.info(sep)
        progress_reporter.info(banner)
        progress_reporter.info(f"       {self.description}")
        progress_reporter.info(sep)

        # Log file output
        self.logger.info(sep)
        self.logger.info("%s", banner)
        self.logger.info("       %s", self.description)
        self.logger.info(sep)

        # Check skip
        if self.config.resume and is_stage_done(project.path, self.name):
            progress_reporter.info("  ✓ Already completed, skipping.")
            self.logger.info("Stage already completed — skipping.")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                project=project.path,
                detail="Already completed (stamp file found)",
            )

        # Dry-run
        if self.config.dry_run:
            progress_reporter.info("  [DRY-RUN] Would execute: %s", self.description)
            self.logger.info("[DRY-RUN] Would execute: %s", self.description)
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                project=project.path,
                detail="Dry-run — not executed",
            )

        # Execute
        try:
            result = self._run_one(project)
        except Exception as exc:
            self.logger.error("Stage failed: %s", exc, exc_info=True)
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"Exception: {exc}",
                error=str(exc),
            )

        # Mark complete
        if result.status == StageStatus.COMPLETED:
            mark_stage_done(project.path, self.name)
            progress_reporter.info(f"  ✓ Completed: {result.detail}")
            self.logger.info("Stage completed successfully.")

        return result

    @abstractmethod
    def _run_one(self, project: ProjectInfo) -> StageResult:
        """Subclass implements actual processing logic here."""
        ...
