"""Shared dataclasses for the tir-stitcher pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ProjectInfo:
    """All known paths for a single TIR project folder."""
    path: Path
    name: str
    raw_dir: Path
    tif_dir: Path
    images_dir: Path
    orthophoto_dir: Path

    @property
    def odm_orthophoto_path(self) -> Path:
        return self.orthophoto_dir / "odm_orthophoto.tif"


@dataclass
class StageResult:
    stage_name: str
    status: StageStatus
    project: Path
    detail: str = ""
    items_processed: int = 0
    items_failed: int = 0
    error: str = ""


@dataclass
class PipelineResult:
    project: ProjectInfo
    stage_results: list = field(default_factory=list)

    @property
    def success(self) -> bool:
        if not self.stage_results:
            return False
        return all(
            r.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
            for r in self.stage_results
        )
