"""Pipeline orchestrator that chains all 6 stages across all discovered projects."""

from __future__ import annotations

import logging

from tir_stitcher.core.config import PipelineConfig
from tir_stitcher.core.discovery import discover_projects
from tir_stitcher.core.logging_setup import get_logger, progress_reporter
from tir_stitcher.core.stage import Stage
from tir_stitcher.core.types import ProjectInfo, PipelineResult, StageResult, StageStatus
from tir_stitcher.stages.copy_exif import CopyExifStage
from tir_stitcher.stages.extract_raw import ExtractRawStage
from tir_stitcher.stages.postprocess import PostprocessStage
from tir_stitcher.stages.prepare_images import PrepareImagesStage
from tir_stitcher.stages.raw_to_tif import RawToTifStage
from tir_stitcher.stages.run_odm import RunODMStage


class PipelineOrchestrator:
    """Manages end-to-end execution of all 6 stages across all discovered projects."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_logger("pipeline")
        self._stages: list[Stage] = self._build_stages()

    @staticmethod
    def _build_stages() -> list[Stage]:
        """Return an empty list — stages need config at init."""
        return []

    def _init_stages(self) -> list[Stage]:
        """Instantiate all stages with the current config."""
        return [
            ExtractRawStage(self.config),
            RawToTifStage(self.config),
            CopyExifStage(self.config),
            PrepareImagesStage(self.config),
            RunODMStage(self.config),
            PostprocessStage(self.config),
        ]

    def run(self, project: Path | None = None) -> list[PipelineResult]:
        """Run all stages over all projects. Returns list of results.

        Args:
            project: Direct project path (skips discovery when set).
        """
        stages = self._init_stages()

        if project is not None:
            project = project.resolve()
            if not project.exists():
                progress_reporter.info("Project directory not found: %s", project)
                self.logger.error("Project directory not found: %s", project)
                return []
            projects = [
                ProjectInfo(
                    path=project,
                    name=project.name,
                    raw_dir=project / "RAW",
                    tif_dir=project / "TIF",
                    images_dir=project / "images",
                    orthophoto_dir=project / "orthophoto",
                )
            ]
        else:
            projects = self._discover()

        if not projects:
            progress_reporter.info("No projects found matching filters.")
            self.logger.warning(
                "No projects found matching filters: %s",
                self.config.discovery.folder_filters,
            )
            return []

        progress_reporter.info("Found %d project(s) to process", len(projects))
        for p in projects:
            progress_reporter.info("  - %s", p.name)
        self.logger.info("Found %d project(s) to process", len(projects))

        results: list[PipelineResult] = []
        for i, project in enumerate(projects):
            result = self._run_project(project, i + 1, len(projects), stages)
            results.append(result)

        self._log_summary(results)
        return results

    def _discover(self) -> list[ProjectInfo]:
        d = self.config.discovery
        paths = discover_projects(
            workspace=self.config.workspace_dir,
            filters=d.folder_filters,
            case_sensitive=d.case_sensitive,
            max_depth=d.max_depth,
            require_images=d.require_images,
        )

        return [
            ProjectInfo(
                path=p,
                name=p.name,
                raw_dir=p / "RAW",
                tif_dir=p / "TIF",
                images_dir=p / "images",
                orthophoto_dir=p / "orthophoto",
            )
            for p in paths
        ]

    def _run_project(
        self,
        project: ProjectInfo,
        step: int,
        total: int,
        stages: list[Stage],
    ) -> PipelineResult:
        sep = "=" * 60
        banner = f"PROJECT [{step}/{total}]: {project.name}"
        progress_reporter.info(sep)
        progress_reporter.info(banner)
        progress_reporter.info(sep)
        self.logger.info(sep)
        self.logger.info(banner)
        self.logger.info(sep)

        pipeline_result = PipelineResult(project=project)

        # Check for existing images/ as indicator that stages 1-4 have been done
        if self.config.resume and project.images_dir.exists():
            progress_reporter.info("  images/ already exists — stages 1-4 will be skipped")
            self.logger.info("images/ exists — skipping stages 1-4 implicitly")

        for stage in stages:
            result = stage.run(project, step=stages.index(stage) + 1, total=len(stages))
            pipeline_result.stage_results.append(result)

            if result.status == StageStatus.FAILED:
                if self.config.stop_on_stage_failure:
                    progress_reporter.info("  ✗ %s failed — stopping", stage.name)
                    self.logger.error(
                        "Stopping project due to stage failure: %s", stage.name
                    )
                    break
                else:
                    progress_reporter.info("  ✗ %s failed — continuing", stage.name)
                    self.logger.warning(
                        "Stage %s failed, continuing to next stage...", stage.name
                    )

        return pipeline_result

    def _log_summary(self, results: list[PipelineResult]) -> None:
        sep = "=" * 60
        progress_reporter.info("")
        progress_reporter.info(sep)
        progress_reporter.info("PIPELINE SUMMARY")
        progress_reporter.info(sep)
        self.logger.info("")
        self.logger.info(sep)
        self.logger.info("PIPELINE SUMMARY")
        self.logger.info(sep)

        # Header
        header = f"{'Project':<50s}"
        for stage in self._init_stages():
            header += f" {stage.name:<14s}"
        self.logger.info(header)
        self.logger.info("-" * len(header))

        # Rows
        success_count = 0
        for pr in results:
            row = f"{pr.project.name:<50s}"
            for stage in self._init_stages():
                sname = stage.name
                found = None
                for sr in pr.stage_results:
                    if sr.stage_name == sname:
                        found = sr
                        break
                if found:
                    status_str = found.status.value[:1].upper()
                    row += f" {status_str:<14s}"
                else:
                    row += f" {'-':<14s}"
            self.logger.info(row)
            if pr.success:
                success_count += 1

        summary = f"Projects fully processed: {success_count}/{len(results)}"
        progress_reporter.info(summary)
        self.logger.info("")
        self.logger.info(summary)

        # List failures in terminal
        failures = [r for r in results if not r.success]
        if failures:
            self.logger.info("Projects with issues:")
            for r in failures:
                failed_stages = [
                    sr.stage_name for sr in r.stage_results
                    if sr.status == StageStatus.FAILED
                ]
                msg = f"  {r.project.name}: {', '.join(failed_stages)}"
                progress_reporter.info(msg)
                self.logger.info(msg)
