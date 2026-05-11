"""Stage 3: Copy GPS EXIF from T.JPG to corresponding TIF files using exiftool.

Each JPG-TIF pair is processed individually to avoid exiftool's multi-source
GPS overwrite bug (where -TagsFromFile applies all sources to all targets).
"""

import subprocess
import time
from pathlib import Path

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import find_executable


class CopyExifStage(Stage):
    name = "copy_exif"
    description = "Copy GPS EXIF metadata from T.JPG to TIF using exiftool"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        ec = self.config.copy_exif
        search_paths = [self.config.workspace_dir]
        if ec.exiftool_path:
            search_paths.insert(0, ec.exiftool_path.parent)

        exiftool = find_executable("exiftool", search_paths=search_paths)
        if exiftool is None:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="exiftool not found. Set copy_exif.exiftool_path in config.",
            )

        self.logger.info("Using exiftool: %s", exiftool)

        from tir_stitcher.core.discovery import discover_t_jpg_files
        tjpg_files = discover_t_jpg_files(project.path)

        if not tjpg_files:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="No T.JPG files found.",
            )

        tif_dir = project.tif_dir
        if not tif_dir.exists():
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"TIF directory not found: {tif_dir}",
            )

        pairs = []
        for jpg in tjpg_files:
            tif_path = tif_dir / f"{jpg.stem}.tif"
            if tif_path.exists():
                pairs.append((jpg, tif_path))

        if not pairs:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="No matching T.JPG <-> TIF pairs found.",
            )

        total = len(pairs)
        failed = 0
        self._progress_start_timer()

        self.logger.info("Found %d JPG-TIF pairs", total)

        for idx, (jpg, tif) in enumerate(pairs, 1):
            try:
                result = subprocess.run(
                    [str(exiftool), "-overwrite_original",
                     "-TagsFromFile", str(jpg), "-gps:all", str(tif)],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    self._progress_log(idx, total)
                else:
                    self.logger.error("exiftool failed for %s: %s",
                                      tif.name, result.stderr.strip()[:200])
                    failed += 1

                if ec.verify_gps and idx == 1 and result.returncode == 0:
                    if self._check_gps(tif, exiftool):
                        self.logger.info("GPS verification passed: %s", tif.name)
                    else:
                        self.logger.warning("GPS verification failed: %s", tif.name)

            except subprocess.TimeoutExpired:
                self.logger.error("exiftool timeout for %s", tif.name)
                failed += 1

        elapsed = time.time() - self._progress_start
        self.logger.info("Done: %d/%d in %.1fs", total - failed, total, elapsed)

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED if failed == 0 else StageStatus.FAILED,
            project=project.path,
            detail=f"EXIF copied for {total - failed}/{total} pairs",
            items_processed=total - failed,
            items_failed=failed,
        )

    @staticmethod
    def _check_gps(tif_path: Path, exiftool: Path) -> bool:
        try:
            result = subprocess.run(
                [str(exiftool), "-GPSLatitude", "-GPSLongitude", str(tif_path)],
                capture_output=True, text=True, timeout=30,
            )
            return "GPS" in result.stdout
        except Exception:
            return False
