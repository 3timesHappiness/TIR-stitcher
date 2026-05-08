"""Stage 6: Extract thermal band from ODM orthophoto to single-band GeoTIFF."""

from pathlib import Path

import rasterio

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus


class PostprocessStage(Stage):
    name = "postprocess"
    description = "Extract thermal band from ODM orthophoto to single-band GeoTIFF"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        src_path = project.odm_orthophoto_path
        if not src_path.exists():
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"Source orthophoto not found: {src_path}",
            )

        # Determine output path
        pp = self.config.postprocess
        if pp.output_dir:
            output_dir = pp.output_dir
        else:
            output_dir = project.path

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{project.name}_TIR.tif"

        if output_path.exists() and output_path.stat().st_size > 0:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                project=project.path,
                detail=f"Output already exists: {output_path}",
            )

        self.logger.info("Source: %s", src_path)
        self.logger.info("Output: %s", output_path)

        try:
            with rasterio.open(src_path) as src:
                # Band 1 contains thermal data (ODM --primary-band 1)
                band_data = src.read(1)

                profile = src.profile.copy()
                profile.update(
                    count=1,
                    dtype="uint16",
                    compress=pp.compression.lower(),
                    predictor=2,
                )
                # Remove RGB-specific metadata
                profile.pop("photometric", None)
                profile.pop("colorinterp", None)
                profile.pop("descriptions", None)

                # Reproject CRS if configured
                if pp.output_crs:
                    profile["crs"] = pp.output_crs

                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(band_data, 1)

                # Write world file for GIS compatibility
                with rasterio.open(output_path, "r+") as dst:
                    dst.nodata = 0

            size_mb = output_path.stat().st_size / (1024 * 1024)
            self.logger.info("Output: %s (%.1f MB, %d×%d)",
                            output_path.name, size_mb, profile["width"], profile["height"])

        except Exception as e:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=str(e),
            )

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            project=project.path,
            detail=f"Extracted thermal band to {output_path.name}",
            items_processed=1,
        )
