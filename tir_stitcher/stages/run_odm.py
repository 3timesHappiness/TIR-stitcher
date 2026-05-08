"""Stage 5: Run OpenDroneMap (Docker) to generate thermal orthophoto."""

import subprocess

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, StageResult, StageStatus
from tir_stitcher.core.utils import find_executable


class RunODMStage(Stage):
    name = "run_odm"
    description = "Run ODM Docker container to generate thermal orthophoto mosaic"

    # Fixed TIR-specific ODM arguments
    TIR_FIXED_ARGS = [
        "--rerun-all",
        "--dsm",
        "--auto-boundary",
        "--radiometric-calibration", "none",
        "--primary-band", "1",
        "--orthophoto-png",
        "--pc-csv",
        "--feature-type", "sift",
    ]

    def _run_one(self, project: ProjectInfo) -> StageResult:
        # Check for existing output
        if project.odm_orthophoto_path.exists() and project.odm_orthophoto_path.stat().st_size > 0:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                project=project.path,
                detail="Orthophoto already exists.",
            )

        # Check Docker
        docker = find_executable("docker")
        if docker is None:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="Docker not found on PATH.",
            )

        # Check that docker daemon is running
        try:
            result = subprocess.run(
                [str(docker), "info"], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    project=project.path,
                    detail="Docker daemon is not running or not accessible.",
                )
        except subprocess.TimeoutExpired:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail="Docker daemon check timed out.",
            )

        # Check images
        images_dir = project.images_dir
        if not images_dir.exists():
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"images/ directory not found: {images_dir}",
            )

        img_count = len([f for f in images_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in (".tif", ".tiff", ".jpg", ".jpeg", ".png")])
        if img_count < 3:
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                project=project.path,
                detail=f"Need at least 3 images for SfM, found {img_count}",
            )

        self.logger.info("Images: %d files in %s", img_count, images_dir)
        self.logger.info("Docker image: %s", self.config.odm.docker_image)

        cmd = self._build_command(project.name)

        self.logger.info("ODM command: %s", " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line and ("ERROR" in line.upper() or "WARN" in line.upper()
                                 or "INFO" in line.upper()):
                        self.logger.info("[ODM] %s", line)

            rc = process.wait()

            if rc != 0:
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    project=project.path,
                    detail=f"ODM exited with code {rc}",
                )

            # Fix up output directory: ODM creates odm_orthophoto/, rename to orthophoto/
            odm_dir = project.path / "odm_orthophoto"
            if odm_dir.exists() and not project.orthophoto_dir.exists():
                odm_dir.rename(project.orthophoto_dir)
                self.logger.info("Renamed odm_orthophoto/ -> orthophoto/")

            # Verify output
            if project.odm_orthophoto_path.exists():
                size_mb = project.odm_orthophoto_path.stat().st_size / (1024 * 1024)
                self.logger.info("Output: %s (%.1f MB)", project.odm_orthophoto_path.name, size_mb)
            else:
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.FAILED,
                    project=project.path,
                    detail="ODM completed but no orthophoto output found.",
                )

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
            detail=f"Generated orthophoto from {img_count} images",
            items_processed=img_count,
        )

    def _build_command(self, project_name: str) -> list[str]:
        odm = self.config.odm
        workspace = self.config.workspace_dir

        cmd = ["docker", "run", "--rm"]

        if odm.use_gpu:
            cmd.append("--gpus")
            cmd.append("all")

        cmd += [
            "-v", f"{workspace}:/datasets",
            odm.docker_image,
            "--project-path", "/datasets", project_name,
        ]

        cmd += self.TIR_FIXED_ARGS
        cmd += [
            "--feature-quality", odm.feature_quality,
            "--pc-quality", odm.pc_quality,
            "--orthophoto-resolution", str(odm.orthophoto_resolution),
            "--dem-resolution", str(odm.dem_resolution),
            "--min-num-features", str(odm.min_num_features),
            "--max-concurrency", str(odm.max_concurrency),
        ]

        if odm.extra_args:
            cmd += odm.extra_args

        return cmd
