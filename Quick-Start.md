# tir-stitcher Quick Start

> For beginners in UAV image processing — no prior experience needed

---

## What is your data?

DJI drones (Mavic 3T, etc.) capture thermal infrared photos (`T.JPG`). These are fundamentally different from regular photos:

| Regular Photo | Thermal Photo (T.JPG) |
|--------------|----------------------|
| Shows color and brightness | Shows temperature |
| RGB, three channels | Single temperature channel |
| No temperature data | Every pixel is a temperature value |

Double-click any `T.JPG` — you'll see a blurry grayscale image. It's not out of focus: thermal infrared resolution is only 640×512 pixels.

---

## What problem does "stitching" solve?

The drone takes hundreds of photos in flight. Each covers only a small patch of ground:

```
Single photo ≈ 60m × 80m        Stitched result ≈ 200m × 280m
┌────┐                          ┌────────────────────┐
│ ██ │                          │████████████████████│
└────┘                          │████████████████████│
                                │████████████████████│
                                └────────────────────┘
```

Stitching merges hundreds of small images into one complete map.

---

## Workflow: 6 Stages

```
Your T.JPG photos
    ↓  ① Extract temperature data (DJI Thermal SDK)
  Raw temperature arrays (.raw)
    ↓  ② Convert to standard image format
  TIF images (no GPS)
    ↓  ③ Embed GPS coordinates into images
  TIF images (with GPS — they know where they are)
    ↓  ④ Place into ODM's input directory
  images/ folder
    ↓  ⑤ ODM auto-aligns and stitches
  Orthophoto mosaic (large image)
    ↓  ⑥ Extract temperature band
  Final result: a temperature map with lat/lon coordinates
```

---

## You only need to worry about 3 things

| Item | Purpose |
|------|---------|
| `config.yaml` | Tell the program: where is your data? Flight altitude? CPU or GPU? |
| `examples/` | 30 sample photos to test with |
| Launch command | `python -m tir_stitcher -c config.yaml` |

The other 18 Python files run automatically — you don't need to touch them.

---

## Hands-on (20 minutes)

### 1. Install dependencies (2 min)

```bash
cd tir-stitcher
pip install -r requirements.txt
```

### 2. Check the config (3 min)

Open `config.yaml` in any text editor, set your data path:

```yaml
workspace_dir: "path/to/your/projects"
```

Everything else works with defaults — each option has comments explaining what it does.

### 3. Dry run first (1 min)

```bash
python -m tir_stitcher -c config.yaml --dry-run
```

Does nothing real, just prints what it *would* do. Check:
- How many projects were found?
- Any missing tools? (e.g., Docker not installed)

### 4. Run for real (10-15 min)

```bash
python -m tir_stitcher -c config.yaml -v
```

The `-v` flag shows detailed progress:

```
[1/6] extract_raw: project_name
      Extract RAW temperature data from T.JPG via DJI Thermal SDK
      Processed 30/30 files

[2/6] raw_to_tif: project_name
      Convert RAW uint16 arrays to single-band TIFF images
      ...

... and so on
```

### 5. Check results

After completion, your project folder will contain:

```
your_project/
├── RAW/                          ← Stage ① output
├── TIF/                          ← Stage ②③ output
├── images/                       ← Stage ④ output
├── orthophoto/
│   └── odm_orthophoto.tif        ← Stage ⑤ output (the stitched mosaic!)
└── project_name_TIR.tif          ← Stage ⑥ final output
```

Open `_TIR.tif` in QGIS to view the completed temperature map.

---

## Required tools

| Tool | Purpose | Download |
|------|---------|----------|
| **Python 3.10+** | Runtime | [python.org](https://www.python.org/) |
| **DJI Thermal SDK** | Extract temperature from T.JPG | `dji_irp.exe` from DJI SDK package(https://www.dji.com/global/downloads/softwares/dji-thermal-sdk?backup_page=index&target=or) |
| **ExifTool** | Write GPS coordinates | [exiftool.org](https://exiftool.org/) |
| **Docker** | Image stitching (Stage ⑤) | [docker.com](https://www.docker.com/) |

Don't have Docker yet? Stages 1-4 still work. Once Docker is installed, the pipeline skips completed stages automatically.

---

## Resume / skip logic

Each completed stage creates a `.tir_stitcher_xxx.done` stamp file in the project folder. On the next run, completed stages are skipped.

**To re-run a specific stage**: delete its `.done` file and run again.

| Re-run... | Delete... |
|-----------|-----------|
| Extract RAW | `.tir_stitcher_extract_raw.done` |
| RAW → TIF | `.tir_stitcher_raw_to_tif.done` |
| Copy EXIF | `.tir_stitcher_copy_exif.done` |
| Prepare images | `.tir_stitcher_prepare_images.done` |
| Run ODM | `.tir_stitcher_run_odm.done` |
| Postprocess | `.tir_stitcher_postprocess.done` |

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| `dji_irp.exe not found` | Set `tsdk.exe_path` in `config.yaml` |
| `exiftool not found` | Set `copy_exif.exiftool_path` in `config.yaml` |
| `Docker not found` | Install Docker Desktop; ensure the tray icon is green |
| `Need at least 3 images` | ODM requires 3+ overlapping photos for SfM |
| RAW size mismatch | Set `raw_to_tif.rows` and `cols` manually in `config.yaml` |
| Stitching fails / black output | Lower `odm.min_num_features` to 4000, or try `feature_quality: high` |

---

## TL;DR

> **Edit `config.yaml` to point to your data, then `python -m tir_stitcher -c config.yaml -v`, and check the `orthophoto/` folder.**
