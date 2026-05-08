"""Stage 3: Copy GPS EXIF from T.JPG to corresponding TIF files using exiftool."""

import os
import subprocess
import tempfile
from pathlib import Path

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import find_executable


class CopyExifStage(Stage):
    name = "copy_exif"
    description = "Copy GPS EXIF metadata from T.JPG to TIF using exiftool"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        # Find exiftool
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

        # Find T.JPG files and matching TIF files
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

        # Build pairs
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

        self.logger.info("Found %d JPG-TIF pairs", len(pairs))
        total = len(pairs)
        failed = 0

        batch_size = ec.batch_size

        for i in range(0, total, batch_size):
            chunk = pairs[i:i + batch_size]

            # Create argfile for batch processing
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as af:
                for jpg, tif in chunk:
                    af.write("-overwrite_original\n")
                    af.write("-TagsFromFile\n")
                    af.write(str(jpg) + "\n")
                    af.write(str(tif) + "\n")
                argfile = af.name

            try:
                cmd = [str(exiftool), "-@", argfile]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    self.logger.error("exiftool batch failed at offset %d: %s",
                                      i, result.stderr.strip()[:500])
                    # Count individual failures
                    for jpg, tif in chunk:
                        if not self._check_gps(tif, exiftool):
                            failed += 1
                else:
                    # Verify GPS was written
                    if ec.verify_gps and i == 0:
                        sample = chunk[0][1]
                        if self._check_gps(sample, exiftool):
                            self.logger.info("GPS verification passed on sample: %s", sample.name)
                        else:
                            self.logger.warning("GPS verification failed on sample: %s", sample.name)
            except subprocess.TimeoutExpired:
                self.logger.error("exiftool batch timeout at offset %d", i)
                failed += len(chunk)
            finally:
                try:
                    os.remove(argfile)
                except OSError:
                    pass

        detail = f"EXIF copied for {total - failed}/{total} pairs"
        if failed > 0:
            detail += f" ({failed} failed)"

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            project=project.path,
            detail=detail,
            items_processed=total - failed,
            items_failed=failed,
        )

    @staticmethod
    def _check_gps(tif_path: Path, exiftool: Path) -> bool:
        """Verify GPS tags exist on a TIF file."""
        try:
            result = subprocess.run(
                [str(exiftool), "-GPSLatitude", "-GPSLongitude", str(tif_path)],
                capture_output=True, text=True, timeout=30,
            )
            return "GPS" in result.stdout
        except Exception:
            return False
