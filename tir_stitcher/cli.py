"""Command-line interface for tir-stitcher."""

from __future__ import annotations

import argparse
from pathlib import Path

from tir_stitcher import __version__
from tir_stitcher.core.config import ConfigError, PipelineConfig
from tir_stitcher.core.logging_setup import get_logger, progress_reporter, setup_logging
from tir_stitcher.pipeline import PipelineOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tir-stitcher",
        description="DJI Thermal Infrared Orthophoto Stitching Pipeline",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.yaml"),
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--project", "-p",
        type=Path,
        default=None,
        help="Direct project path (skips discovery when set)",
    )
    parser.add_argument(
        "--workspace", "-w",
        type=Path,
        default=None,
        help="Override workspace directory from config",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tir-stitcher {__version__}",
    )
    return parser


def main(args: argparse.Namespace | None = None) -> int:
    parser = build_parser()
    if args is None:
        args = parser.parse_args()

    # Load config
    config_path = args.config.resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        print("Create one by copying and editing the default config.yaml template.")
        return 1

    try:
        config = PipelineConfig.from_yaml(config_path)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        return 1

    # CLI overrides
    if args.workspace:
        config.workspace_dir = args.workspace.resolve()
    if args.dry_run:
        config.dry_run = True
    if args.verbose:
        config.verbose = True

    # Setup logging
    log_dir = config.log_dir or (config.workspace_dir / "logs")
    setup_logging(log_dir, verbose=config.verbose)
    logger = get_logger("cli")

    progress_reporter.info("tir-stitcher v%s", __version__)
    progress_reporter.info("Config: %s", config_path)
    progress_reporter.info("Workspace: %s", config.workspace_dir)
    logger.info("tir-stitcher v%s", __version__)
    logger.info("Config: %s", config_path)
    logger.info("Workspace: %s", config.workspace_dir)
    if config.dry_run:
        progress_reporter.info("DRY-RUN MODE — no changes will be made")
        logger.info("DRY-RUN MODE — no changes will be made")

    # Run pipeline
    orchestrator = PipelineOrchestrator(config)
    results = orchestrator.run(args.project)

    if not results:
        logger.info("No projects processed.")
        return 0

    all_ok = all(r.success for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
