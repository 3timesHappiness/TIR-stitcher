"""Stage 1: Convert T.JPG to RAW using DJI Thermal SDK (dji_irp.exe)."""

import subprocess
import time
from pathlib import Path

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import find_executable


class ExtractRawStage(Stage):
    name = "extract_raw"
    description = "Extract RAW temperature data from T.JPG via DJI Thermal SDK"

    def _run_one(self, project: ProjectInfo) -> StageResult:
        # Find SDK
        tsdk_config = self.config.tsdk
        search_paths = [self.config.workspace_dir]
        if tsdk_config.exe_path:
            search_paths.insert(0, tsdk_config.exe_path.parent)

        sdk_exe = find_executable("dji_irp", search_paths=search_paths, search_recursive=True)
        if sdk_exe is None:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="dji_irp.exe not found. Set tsdk.exe_path in config or place SDK in workspace.",
            )

        self.logger.info("Using DJI Thermal SDK: %s", sdk_exe)

        # Find T.JPG files
        from tir_stitcher.core.discovery import discover_t_jpg_files
        tjpg_files = discover_t_jpg_files(project.path)

        if not tjpg_files:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="No T.JPG files found in project root.",
            )

        self.logger.info("Found %d T.JPG files", len(tjpg_files))

        raw_dir = project.raw_dir
        raw_dir.mkdir(exist_ok=True)

        params = {
            "measurefmt": tsdk_config.measurefmt,
            "distance": tsdk_config.distance,
            "humidity": tsdk_config.humidity,
            "emissivity": tsdk_config.emissivity,
            "ambient": tsdk_config.ambient,
            "reflection": tsdk_config.reflection,
        }

        total = len(tjpg_files)
        processed = 0
        failed = 0
        self._progress_start_timer()

        for idx, tjpg in enumerate(tjpg_files, 1):
            out_file = raw_dir / f"{tjpg.stem}.raw"

            if out_file.exists() and out_file.stat().st_size > 0:
                processed += 1
                self._progress_log(idx, total)
                continue

            cmd = [
                str(sdk_exe),
                "-s", str(tjpg),
                "-a", "measure",
                "-o", str(out_file),
                "--measurefmt", str(params["measurefmt"]),
                "--distance", str(params["distance"]),
                "--humidity", str(params["humidity"]),
                "--emissivity", str(params["emissivity"]),
                "--ambient", str(params["ambient"]),
                "--reflection", str(params["reflection"]),
            ]

            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
                processed += 1
                self._progress_log(idx, total)
            except subprocess.CalledProcessError as e:
                self.logger.error("SDK failed for %s: %s", tjpg.name, e.stderr.strip() if e.stderr else str(e))
                failed += 1
            except subprocess.TimeoutExpired:
                self.logger.error("SDK timeout for %s", tjpg.name)
                failed += 1

        elapsed = time.time() - self._progress_start
        self.logger.info("Done: %d/%d in %.1fs", processed, total, elapsed)

        detail = f"Processed {processed}/{total} files"
        if failed > 0:
            detail += f" ({failed} failed)"

        return StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED if failed == 0 else StageStatus.FAILED,
            project=project.path,
            detail=detail,
            items_processed=processed,
            items_failed=failed,
        )
