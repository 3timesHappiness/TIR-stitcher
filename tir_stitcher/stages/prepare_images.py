"""Stage 4: Make TIF files available to ODM in the images/ folder."""

import os
import shutil
from pathlib import Path

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus


class PrepareImagesStage(Stage):
    name = "prepare_images"
    description = "Copy/link TIF images into images/ folder for ODM processing"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        tif_dir = project.tif_dir
        if not tif_dir.exists():
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"TIF directory not found: {tif_dir}",
            )

        tif_files = sorted(tif_dir.glob("*.tif")) + sorted(tif_dir.glob("*.tiff"))
        if not tif_files:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="No TIF files found.",
            )

        self.logger.info("Found %d TIF files", len(tif_files))

        images_dir = project.images_dir
        images_dir.mkdir(exist_ok=True)

        mode = self.config.prepare_images.mode
        self.logger.info("Mode: %s", mode)

        processed = 0
        failed = 0

        for src in tif_files:
            dst = images_dir / src.name
            if dst.exists():
                # Skip if same size
                if dst.stat().st_size == src.stat().st_size:
                    processed += 1
                    continue
                else:
                    dst.unlink()

            try:
                if mode == "copy":
                    shutil.copy2(src, dst)
                elif mode == "symlink":
                    if dst.exists():
                        dst.unlink()
                    os.symlink(src, dst)
                elif mode == "hardlink":
                    if dst.exists():
                        dst.unlink()
                    os.link(src, dst)
                processed += 1
            except OSError as e:
                self.logger.error("Failed to %s %s: %s", mode, src.name, e)
                failed += 1

        detail = f"{mode}d {processed}/{len(tif_files)} files"
        if failed > 0:
            detail += f" ({failed} failed)"

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED if failed == 0 else StageStatus.COMPLETED,
            project=project.path,
            detail=detail,
            items_processed=processed,
            items_failed=failed,
        )
