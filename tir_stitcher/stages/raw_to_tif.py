"""Stage 2: Convert RAW (uint16) to single-band TIFF images."""

from pathlib import Path

import numpy as np
import cv2

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import auto_detect_dimensions


class RawToTifStage(Stage):
    name = "raw_to_tif"
    description = "Convert RAW uint16 arrays to single-band TIFF images"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        raw_dir = project.raw_dir
        if not raw_dir.exists() or not any(raw_dir.iterdir()):
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"RAW directory empty or missing: {raw_dir}",
            )

        raw_files = sorted([p for p in raw_dir.iterdir() if p.suffix.lower() == ".raw"])
        if not raw_files:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="No .raw files found in RAW directory.",
            )

        self.logger.info("Found %d RAW files", len(raw_files))

        # Determine dimensions
        rtc = self.config.raw_to_tif
        if rtc.rows and rtc.cols:
            rows, cols = rtc.rows, rtc.cols
            self.logger.info("Using configured dimensions: %dx%d", rows, cols)
        else:
            try:
                rows, cols = auto_detect_dimensions(raw_files[0], rtc.channels)
                self.logger.info("Auto-detected dimensions: %dx%d", rows, cols)
            except ValueError as e:
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    project=project.path,
                    detail=str(e),
                )

        expected_bytes = rows * cols * rtc.channels * 2  # uint16 = 2 bytes

        tif_dir = project.tif_dir
        tif_dir.mkdir(exist_ok=True)

        processed = 0
        failed = 0
        for rp in raw_files:
            tif_path = tif_dir / f"{rp.stem}.tif"

            if tif_path.exists() and tif_path.stat().st_size > 0:
                processed += 1
                continue

            # Validate file size
            actual = rp.stat().st_size
            if actual != expected_bytes:
                self.logger.error(
                    "Skipping %s: expected %d bytes, got %d bytes",
                    rp.name, expected_bytes, actual,
                )
                failed += 1
                continue

            try:
                data = np.fromfile(str(rp), dtype=np.uint16)
                if rtc.channels == 1:
                    img = data.reshape((rows, cols))
                else:
                    img = data.reshape((rows, cols, rtc.channels))
                cv2.imwrite(str(tif_path), img)
                processed += 1
            except Exception as e:
                self.logger.error("Failed to convert %s: %s", rp.name, e)
                failed += 1

        detail = f"Converted {processed}/{len(raw_files)} files"
        if failed > 0:
            detail += f" ({failed} failed)"

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            project=project.path,
            detail=detail,
            items_processed=processed,
            items_failed=failed,
        )
