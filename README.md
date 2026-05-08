# tir-stitcher

**DJI Thermal Infrared Orthophoto Stitching Pipeline**
大疆无人机热红外正射影像拼接流水线

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A modular, configurable pipeline that converts DJI drone thermal images (T.JPG R-JPEG) into georeferenced single-band temperature orthophoto mosaics.

---

## Pipeline Overview

```
T.JPG ──[DJI Thermal SDK]──> RAW ──[numpy+cv2]──> TIF
  │                                                     │
  └──────────────────[exiftool]─────────────────────────┘
                            │
                   TIF + GPS EXIF
                            │
                     [copy to images/]
                            │
                   [ODM Docker SfM]
                            │
                      orthophoto
                            │
                    [rasterio band extract]
                            │
                 single-band GeoTIFF (EPSG:4326)
```

| Stage | Description | Input | Output |
|-------|-------------|-------|--------|
| 1. extract_raw | Extract temperature via DJI Thermal SDK | `*.T.JPG` | `RAW/*.raw` (uint16) |
| 2. raw_to_tif | Convert RAW arrays to TIFF images | `RAW/*.raw` | `TIF/*.tif` (uint16, 640x512) |
| 3. copy_exif | Copy GPS EXIF from JPG to TIF | `*.T.JPG` + `TIF/*.tif` | `TIF/*.tif` (with GPS) |
| 4. prepare_images | Make TIFs available for ODM | `TIF/*.tif` | `images/*.tif` |
| 5. run_odm | SfM + orthomosaic via Docker ODM | `images/*.tif` | `orthophoto/odm_orthophoto.tif` |
| 6. postprocess | Extract temperature band to GeoTIFF | `odm_orthophoto.tif` | `{project}_TIR.tif` |

---

## Requirements

### System Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.10+** | Runtime | [python.org](https://www.python.org/) |
| **DJI Thermal SDK** | RAW extraction from T.JPG | Included in DJI SDK package (`dji_irp.exe`) |
| **ExifTool** | GPS EXIF transfer | [exiftool.org](https://exiftool.org/) |
| **Docker** | ODM orthophoto generation | [docker.com](https://www.docker.com/) |

### Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Quick Start

### 1. Prepare your workspace

Place DJI TIR project folders in a workspace directory. Each project folder should contain:
- `*.T.JPG` files at the project root (DJI thermal R-JPEG images with embedded temperature data)
- Folder names should contain "DJI" and "TIR" (configurable)

```
workspace/
├── DJI_202505241319_003_TIR43m/
│   ├── DJI_20250524132107_0001_T.JPG
│   ├── DJI_20250524132108_0002_T.JPG
│   └── ...
├── DJI_202505251354_003_hongxingTIR43m/
│   ├── DJI_20250525135620_0001_T.JPG
│   └── ...
└── ...
```

### 2. Edit configuration

```bash
cp config.yaml my_config.yaml
# Edit my_config.yaml:
#   - Set workspace_dir to your project directory
#   - Adjust TSDK distance/emissivity/humidity for your flight conditions
#   - Set odm.use_gpu: true if you have NVIDIA Docker runtime
```

### 3. Dry-run (check everything)

```bash
python -m tir_stitcher --config my_config.yaml --dry-run --verbose
```

### 4. Run the pipeline

```bash
python -m tir_stitcher --config my_config.yaml --verbose
```

The pipeline skips already-completed stages automatically. Delete a project's `.tir_stitcher_*.done` stamp files to re-run specific stages.

---

## Configuration Reference

See `config.yaml` for all options with comments. Key settings:

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `tsdk` | `distance` | 5.0 | Flight altitude (meters) |
| `tsdk` | `emissivity` | 0.95 | Surface emissivity |
| `odm` | `use_gpu` | false | Enable GPU acceleration |
| `odm` | `docker_image` | `opendronemap/odm` | CPU image (or `:gpu` tag) |
| `pipeline` | `resume` | true | Skip completed stages |
| `pipeline` | `stop_on_stage_failure` | false | Abort on first failure |

---

## ODM Parameters for TIR

The pipeline uses these fixed ODM arguments optimized for thermal infrared:

```
--radiometric-calibration none     # Preserve raw temperature values
--primary-band 1                   # Single-band thermal data
--feature-type sift                # SIFT handles thermal gradients better
--orthophoto-png                   # Lossless output
--pc-csv                           # Point cloud with temperature values
```

---

## Output

### Per-project output

```
project/
├── RAW/                            # Raw uint16 temperature arrays
├── TIF/                            # TIFF images with GPS EXIF
├── images/                         # Copy of TIF for ODM input
├── orthophoto/                     # ODM output
│   ├── odm_orthophoto.tif          # Multi-band orthophoto
│   ├── odm_orthophoto.png          # PNG preview
│   └── ...
├── {project_name}_TIR.tif         # Final single-band GeoTIFF
├── .tir_stitcher_extract_raw.done  # Stage completion stamps
├── .tir_stitcher_raw_to_tif.done
└── ...
```

### Logs

```
workspace/logs/
├── pipeline.log                    # Central aggregated log
└── {project_name}.log             # Per-project detail log
```

---

## Re-running Specific Stages

Delete the corresponding stamp file in the project folder:

| To re-run... | Delete... |
|--------------|-----------|
| Extract RAW | `.tir_stitcher_extract_raw.done` |
| RAW → TIF | `.tir_stitcher_raw_to_tif.done` |
| Copy EXIF | `.tir_stitcher_copy_exif.done` |
| Prepare images | `.tir_stitcher_prepare_images.done` |
| Run ODM | `.tir_stitcher_run_odm.done` |
| Postprocess | `.tir_stitcher_postprocess.done` |

Then re-run `python -m tir_stitcher --config my_config.yaml`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `dji_irp.exe not found` | Set `tsdk.exe_path` in config or place SDK in workspace |
| `exiftool not found` | Set `copy_exif.exiftool_path` in config or add to PATH |
| `Docker not found` | Install Docker Desktop and ensure daemon is running |
| `Need at least 3 images` | ODM requires 3+ overlapping images for SfM |
| RAW size mismatch | Set `raw_to_tif.rows` and `raw_to_tif.cols` manually |
| ODM feature matching fails | Try lowering `odm.min_num_features` or use `odm.feature_quality: high` |
| Symlink fails on Windows | Use `prepare_images.mode: copy` or enable Developer Mode |

---

## Project Structure

```
tir-stitcher/
├── README.md
├── requirements.txt
├── config.yaml
└── tir_stitcher/
    ├── __init__.py
    ├── __main__.py
    ├── pipeline.py              # PipelineOrchestrator
    ├── cli.py                   # CLI entry point
    ├── core/
    │   ├── __init__.py
    │   ├── config.py            # Config dataclass + YAML
    │   ├── logging_setup.py     # Unified logging
    │   ├── discovery.py         # Project scanner
    │   ├── utils.py             # Cross-platform helpers
    │   ├── stage.py             # Stage ABC
    │   └── types.py             # Shared dataclasses
    └── stages/
        ├── __init__.py
        ├── extract_raw.py       # Stage 1: T.JPG → RAW
        ├── raw_to_tif.py        # Stage 2: RAW → TIF
        ├── copy_exif.py         # Stage 3: EXIF copy
        ├── prepare_images.py    # Stage 4: images/ setup
        ├── run_odm.py           # Stage 5: ODM orthophoto
        └── postprocess.py       # Stage 6: band extraction
```

---

## License

MIT License — see [LICENSE](LICENSE) file for details.
