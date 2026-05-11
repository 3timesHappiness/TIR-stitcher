"""Stage 6: Extract thermal band from ODM orthophoto to single-band GeoTIFF.

Preserves ODM's original CRS by default. Only reprojects if the user explicitly
requests a different output_crs and it differs from the source CRS.
"""

from pathlib import Path

import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

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
                band_data = src.read(1)
                src_crs = src.crs

                profile = src.profile.copy()
                profile.update(
                    count=1,
                    dtype="uint16",
                    compress=pp.compression.lower(),
                    predictor=2,
                )
                profile.pop("photometric", None)
                profile.pop("colorinterp", None)
                profile.pop("descriptions", None)

                # Determine target CRS
                target_crs_str = pp.output_crs.strip() if pp.output_crs else None
                if target_crs_str:
                    target_crs = rasterio.crs.CRS.from_string(target_crs_str)
                else:
                    target_crs = None

                needs_reproject = (
                    target_crs is not None
                    and src_crs is not None
                    and target_crs != src_crs
                )

                if needs_reproject:
                    self.logger.info("Reprojecting: %s -> %s", src_crs, target_crs)
                    transform, width, height = calculate_default_transform(
                        src_crs, target_crs,
                        src.width, src.height,
                        *src.bounds,
                    )
                    profile.update(
                        crs=target_crs,
                        transform=transform,
                        width=width,
                        height=height,
                    )
                    with rasterio.open(output_path, "w", **profile) as dst:
                        reproject(
                            source=band_data,
                            destination=rasterio.band(dst, 1),
                            src_transform=src.transform,
                            src_crs=src_crs,
                            dst_transform=transform,
                            dst_crs=target_crs,
                            resampling=Resampling.nearest,
                        )
                else:
                    # Keep original CRS — no reprojection needed
                    if target_crs:
                        profile["crs"] = target_crs
                    with rasterio.open(output_path, "w", **profile) as dst:
                        dst.write(band_data, 1)

                # Set nodata
                with rasterio.open(output_path, "r+") as dst:
                    dst.nodata = 0

            size_mb = output_path.stat().st_size / (1024 * 1024)
            self.logger.info("Output: %s (%.1f MB, %d×%d, %s)",
                             output_path.name, size_mb,
                             profile["width"], profile["height"],
                             profile.get("crs", src_crs))

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
