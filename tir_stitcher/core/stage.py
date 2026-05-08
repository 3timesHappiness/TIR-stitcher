"""Abstract base class for pipeline stages."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import is_stage_done, mark_stage_done


class Stage(ABC):
    """Base class for a pipeline stage with skip/resume and dry-run support."""

    name: str = ""
    description: str = ""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logging.getLogger(f"tir_stitcher.stages.{self.name}")

    def run(self, project: ProjectInfo, step: int = 0, total: int = 0) -> StageResult:
        """Public entry point: check skip, run, write stamp, return result."""

        banner = f"[{step}/{total}] {self.name}: {project.name}" if total else f"{self.name}: {project.name}"
        self.logger.info("=" * 60)
        self.logger.info("%s", banner)
        self.logger.info("       %s", self.description)
        self.logger.info("=" * 60)

        # Check skip
        if self.config.resume and is_stage_done(project.path, self.name):
            self.logger.info("Stage already completed — skipping.")
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                project=project.path,
                detail="Already completed (stamp file found)",
            )

        # Dry-run
        if self.config.dry_run:
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
            self.logger.info("Stage completed successfully.")

        return result

    @abstractmethod
    def _run_one(self, project: ProjectInfo) -> StageResult:
        """Subclass implements actual processing logic here."""
        ...
