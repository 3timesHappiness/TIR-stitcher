"""Configuration dataclass and YAML loader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Invalid configuration."""


@dataclass
class TSDKConfig:
    exe_path: Path | None = None
    distance: float = 5.0
    humidity: float = 50.0
    emissivity: float = 0.95
    ambient: float = 25.0
    reflection: float = 25.0
    measurefmt: int = 0


@dataclass
class RawToTifConfig:
    rows: int | None = None
    cols: int | None = None
    channels: int = 1


@dataclass
class CopyExifConfig:
    exiftool_path: Path | None = None
    batch_size: int = 5000
    verify_gps: bool = True


@dataclass
class PrepareImagesConfig:
    mode: str = "copy"


@dataclass
class ODMConfig:
    docker_image: str = "opendronemap/odm"
    docker_path: Path | None = None
    use_gpu: bool = False
    feature_quality: str = "ultra"
    pc_quality: str = "ultra"
    orthophoto_resolution: float = 5.0
    dem_resolution: float = 5.0
    min_num_features: int = 10000
    max_concurrency: int = 32
    extra_args: list[str] = field(default_factory=list)


@dataclass
class PostprocessConfig:
    output_dir: Path | None = None
    output_crs: str | None = None
    compression: str = "LZW"


@dataclass
class DiscoveryConfig:
    folder_filters: list[str] = field(default_factory=lambda: ["DJI", "TIR"])
    case_sensitive: bool = False
    max_depth: int = 2
    require_images: bool = True


@dataclass
class PipelineConfig:
    workspace_dir: Path
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    tsdk: TSDKConfig = field(default_factory=TSDKConfig)
    raw_to_tif: RawToTifConfig = field(default_factory=RawToTifConfig)
    copy_exif: CopyExifConfig = field(default_factory=CopyExifConfig)
    prepare_images: PrepareImagesConfig = field(default_factory=PrepareImagesConfig)
    odm: ODMConfig = field(default_factory=ODMConfig)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    stop_on_stage_failure: bool = False
    resume: bool = True
    dry_run: bool = False
    log_dir: Path | None = None
    verbose: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> PipelineConfig:
        """Load and validate configuration from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ConfigError(f"Empty config file: {path}")

        # Top-level workspace_dir is required
        if "workspace_dir" not in data:
            raise ConfigError("Missing required field: workspace_dir")

        cfg = cls._parse(data)
        cfg.validate()
        return cfg

    @classmethod
    def _parse(cls, data: dict[str, Any]) -> PipelineConfig:
        workspace = Path(os.path.expandvars(data["workspace_dir"])).resolve()

        discovery = DiscoveryConfig()
        if "discovery" in data:
            d = data["discovery"]
            if "folder_filters" in d:
                discovery.folder_filters = d["folder_filters"]
            if "case_sensitive" in d:
                discovery.case_sensitive = d["case_sensitive"]
            if "max_depth" in d:
                discovery.max_depth = d["max_depth"]
            if "require_images" in d:
                discovery.require_images = d["require_images"]

        tsdk = TSDKConfig()
        if "tsdk" in data:
            t = data["tsdk"]
            if "exe_path" in t and t["exe_path"]:
                tsdk.exe_path = Path(os.path.expandvars(t["exe_path"]))
            for key in ("distance", "humidity", "emissivity", "ambient", "reflection", "measurefmt"):
                if key in t:
                    setattr(tsdk, key, t[key])

        raw_cfg = RawToTifConfig()
        if "raw_to_tif" in data:
            r = data["raw_to_tif"]
            for key in ("rows", "cols", "channels"):
                if key in r:
                    setattr(raw_cfg, key, r[key])

        exif = CopyExifConfig()
        if "copy_exif" in data:
            e = data["copy_exif"]
            if "exiftool_path" in e and e["exiftool_path"]:
                exif.exiftool_path = Path(os.path.expandvars(e["exiftool_path"]))
            if "batch_size" in e:
                exif.batch_size = e["batch_size"]
            if "verify_gps" in e:
                exif.verify_gps = e["verify_gps"]

        prep = PrepareImagesConfig()
        if "prepare_images" in data:
            p = data["prepare_images"]
            if "mode" in p:
                prep.mode = p["mode"]

        odm = ODMConfig()
        if "odm" in data:
            o = data["odm"]
            for key in ("docker_image", "feature_quality", "pc_quality", "use_gpu"):
                if key in o:
                    setattr(odm, key, o[key])
            for key in ("orthophoto_resolution", "dem_resolution", "min_num_features", "max_concurrency"):
                if key in o:
                    setattr(odm, key, o[key])
            if "docker_path" in o and o["docker_path"]:
                odm.docker_path = Path(os.path.expandvars(o["docker_path"]))
            if "extra_args" in o:
                odm.extra_args = o["extra_args"]

        post = PostprocessConfig()
        if "postprocess" in data:
            pp = data["postprocess"]
            if "output_dir" in pp and pp["output_dir"]:
                post.output_dir = Path(os.path.expandvars(pp["output_dir"]))
            if "output_crs" in pp:
                post.output_crs = pp["output_crs"]
            if "compression" in pp:
                post.compression = pp["compression"]

        pipeline_cfg = cls(
            workspace_dir=workspace,
            discovery=discovery,
            tsdk=tsdk,
            raw_to_tif=raw_cfg,
            copy_exif=exif,
            prepare_images=prep,
            odm=odm,
            postprocess=post,
        )

        if "pipeline" in data:
            p = data["pipeline"]
            for key in ("stop_on_stage_failure", "resume", "dry_run", "verbose"):
                if key in p:
                    setattr(pipeline_cfg, key, p[key])
            if "log_dir" in p and p["log_dir"]:
                pipeline_cfg.log_dir = Path(os.path.expandvars(p["log_dir"]))

        return pipeline_cfg

    def validate(self) -> None:
        """Raise ConfigError if configuration is invalid."""
        if not self.workspace_dir.exists():
            raise ConfigError(f"workspace_dir does not exist: {self.workspace_dir}")

        if not self.discovery.folder_filters:
            raise ConfigError("discovery.folder_filters must not be empty")

        mode = self.prepare_images.mode
        if mode not in ("copy", "symlink", "hardlink"):
            raise ConfigError(f"prepare_images.mode must be copy/symlink/hardlink, got: {mode}")

        if mode == "symlink" and os.name == "nt":
            import logging
            logging.getLogger("tir_stitcher").warning(
                "Symlink mode on Windows requires admin privileges or developer mode"
            )

        if not (0.0 <= self.tsdk.emissivity <= 1.0):
            raise ConfigError(f"Emissivity must be 0.0-1.0, got {self.tsdk.emissivity}")
