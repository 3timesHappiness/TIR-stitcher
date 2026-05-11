# TIR-stitcher

**DJI Thermal Infrared Orthophoto Stitching Pipeline**  
大疆无人机热红外正射影像拼接流水线

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

将 DJI 无人机热红外照片（T.JPG）自动拼接为带地理坐标的单波段温度正射影像。

> **零基础可用：** 改好配置 → 一行命令 → 得到拼接结果。

## 快速上手（20 分钟）

### 1. 准备数据

把 DJI 热红外项目文件夹放到 workspace 目录下，每个项目文件夹根目录直接包含 `*_T.JPG` 文件：

```
workspace/                           ← 设为 workspace_dir，需要在yaml中写入工作路径
├── DJI_20250524_003_TIR43m/         ← 一个项目文件夹
│   ├── DJI_20250524132107_0001_T.JPG  ← T.JPG 在项目根目录
│   ├── DJI_20250524132108_0002_T.JPG
│   └── ...
├── DJI_20250525_004_TIR43m/         ← 另一个项目文件夹
│   ├── DJI_20250525135620_0001_T.JPG
│   └── ...
└── config.yaml                      ← 配置文件（放在任意位置，通过 -c 指定）
```

> **关键：** T.JPG 必须直接放在项目文件夹的根目录下，不能放在子文件夹里。在流程中会自动扫描项目根目录下的 `*_T.JPG` 文件。

`config.yaml` 不需要放在 workspace 里，放在任意位置，运行时用 `-c` 指定路径即可。

### 2. 修改配置

用文本编辑器打开 `config.yaml`：

```yaml
# 必改项：
workspace_dir: "你的workspace路径"

# 按需改：
tsdk:
  distance: 5.0          # 飞行高度 (米)
  emissivity: 0.95       # 地表发射率

odm:
  # Windows Git Bash 用户如果提示 docker 找不到，设这个：
  docker_path: "C:/Program Files/Docker/Docker/resources/bin"
```

### 3. 激活虚拟环境（推荐）

建议使用虚拟环境避免依赖冲突。

**conda 环境：**
```bash
conda create -n tir python=3.11
conda activate tir
pip install -r requirements.txt

# 后续运行时：
conda run -n tir python -m tir_stitcher -c config.yaml
```

**Python venv：**
```bash
python -m venv venv
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate       # Windows CMD
pip install -r requirements.txt

# 后续运行时（先激活环境）：
python -m tir_stitcher -c config.yaml
```

### 4. 假装跑一遍（检查环境）

```bash
# conda 环境用这种方式：
conda run -n tir python -m tir_stitcher -c config.yaml --dry-run

# 普通 venv 或全局环境：
python -m tir_stitcher -c config.yaml --dry-run
```

不真实执行，只打印会做什么。确认：
- 找到了几个项目？
- 有没有工具缺失提示？

### 5. 正式运行

```bash
# conda 环境：
conda run -n tir python -m tir_stitcher -c config.yaml

# 普通环境：
python -m tir_stitcher -c config.yaml
```

终端会实时显示处理进度和预计剩余时间：

```
[1/6] extract_raw: 项目名
       Extract RAW temperature data from T.JPG via DJI Thermal SDK
  [45/100] 45% | 12s elapsed | ~15s remaining
```

`-v` 仅在调试时使用，会把所有详细日志也输出到终端。

或者用 `--project` / `-p` 直接指定单个项目（跳过自动发现）：

```bash
# conda 环境：
conda run -n tir python -m tir_stitcher -c config.yaml -p "你的项目路径"

# 普通环境：
python -m tir_stitcher -c config.yaml -p "你的项目路径"
```

### 6. 查看结果

运行结束后，项目文件夹里会多出：

```
你的项目/
├── RAW/                          ← 阶段① 产物
├── TIF/                          ← 阶段②③ 产物 (带 GPS 的 TIF)
├── images/                       ← 阶段④ 产物
├── orthophoto/
│   ├── odm_orthophoto.tif        ← 阶段⑤ 产物 (拼接大图)
│   └── odm_orthophoto.png        ← 预览图
└── 项目名_TIR.tif                ← 阶段⑥ 最终输出 (单波段温度 GeoTIFF)
```

用 **QGIS** 打开 `_TIR.tif` 即可查看拼接好的温度地图。

---

## 你的数据是什么？

DJI 无人机（Mavic 3T 等）拍摄的 `T.JPG` ：

| 普通照片 | 热红外照片 (T.JPG) |
|---------|-------------------|
| 看到颜色和亮度 | 看到温度 |
| RGB 三通道 | 单通道温度值 |
| 高分辨率 | 分辨率为 640×512 像素 |


---

## 工作流：6 个阶段

```
你的 T.JPG 照片
    ↓  ① 提取温度数据 (DJI Thermal SDK)
  温度数组 (.raw)
    ↓  ② 转为标准图像格式 (numpy + OpenCV)
  TIF 图像 (无 GPS)
    ↓  ③ 逐对嵌入 GPS 坐标 (ExifTool)
  TIF 图像 (带 GPS，知道自己在哪)
    ↓  ④ 放入 images/ 目录
  images/ 文件夹
    ↓  ⑤ ODM Docker 自动配准 + 拼接 (SfM)
  正射镶嵌图 (大图)
    ↓  ⑥ 提取温度波段
  最终结果: 一张带地理坐标的温度地图
```

---

## 需要安装什么

| 工具 | 用途 | 下载 / 说明 |
|------|------|-------------|
| **Python 3.10+** | 运行环境 | [python.org](https://www.python.org/) |
| **DJI Thermal SDK** | 从 T.JPG 提取温度 | [DJI 下载中心](https://www.dji.com/global/downloads/softwares/dji-thermal-sdk) |
| **ExifTool** | GPS 坐标写入 TIF | [exiftool.org](https://exiftool.org/)，下载后改名为 `exiftool.exe` |
| **Docker Desktop** | 图像拼接 (阶段⑤) | [docker.com](https://www.docker.com/) |

**Python 依赖：**
```bash
pip install -r requirements.txt
```

没有 Docker 也可以先跑阶段①-④，Docker 装好后会自动跳过已完成阶段。

### Windows 环境注意事项

- **Docker PATH 问题：** 如果在命令行中提示 `Docker not found`，在 `config.yaml` 中设置 `odm.docker_path` 指向 Docker 安装目录的 `bin` 子目录（通常是 `C:/Program Files/Docker/Docker/resources/bin`）。也可以在 CMD 或 PowerShell 中运行，它们通常能自动找到 Docker。
- **ExifTool 安装：** 下载 Windows 版后，将 `exiftool(-k).exe` 重命名为 `exiftool.exe`，放到 PATH 中的目录或通过 `copy_exif.exiftool_path` 指定。
- **推荐使用 conda 虚拟环境**，避免依赖冲突。
- **Symlink 模式需管理员权限**，推荐用 `copy` 模式（默认）。

---

## Docker 与 ODM 环境配置

阶段⑤的图像拼接依赖 [OpenDroneMap](https://www.opendronemap.org/) (ODM)，它通过 Docker 容器运行。

### 1. 安装 Docker Desktop

从 [docker.com](https://www.docker.com/) 下载并安装 Docker Desktop。安装完成后：
- Windows 右下角系统托盘出现 Docker 图标，确保在运行中
- 在 **CMD** 或 **PowerShell** 中验证：`docker info`
- **Git Bash 用户注意：** Docker 的 `docker` 命令可能不在 Git Bash 的 PATH 中。可以用下面两种方式解决：
  - **方式 A（推荐）：** 在 `config.yaml` 中设置 `odm.docker_path`
  - **方式 B：** 在 CMD 或 PowerShell 中运行 tir-stitcher

### 2. 拉取 ODM 镜像

```bash
docker pull opendronemap/odm
```

镜像约 2-3 GB，只需下载一次。如果想用 GPU 加速，拉取 `opendronemap/odm:gpu` 标签。

### 3. 配置 config.yaml

```yaml
odm:
  docker_image: "opendronemap/odm"      # CPU 版镜像
  docker_path: null                      # Docker 可执行文件所在目录
                                         # Windows 用户如果 Git Bash 提示 docker 找不到，
                                         # 设为你的 Docker 安装路径下的 bin 目录，例如：
                                         #   docker_path: "C:/Program Files/Docker/Docker/resources/bin"
  use_gpu: false                         # GPU 加速（需 NVIDIA Docker runtime）
  feature_quality: "high"                # 特征提取质量: ultra / high / medium / low
  pc_quality: "high"                     # 点云质量: ultra / high / medium / low
  min_num_features: 3000                 # 最小特征点数，热红外建议 2000-4000
  orthophoto_resolution: 5.0             # 正射影像分辨率 (cm/pixel)
  dem_resolution: 5.0                    # DEM 分辨率 (cm/pixel)
```

### 4. Docker 如何挂载数据

ODM 运行在容器内部，需要把数据挂载进去。在流程中自动处理这一步：

- **发现模式：** 将 `workspace_dir` 整个目录挂载到容器内 `/datasets`，项目文件夹作为子目录
- **`--project` 模式：** 将项目所在父目录挂载到 `/datasets`，自动处理非 workspace 根目录下的项目

如果出现 `Need at least 3 images` 但 images/ 里确实有文件，通常是因为挂载路径不对——检查项目文件夹是否在 `workspace_dir` 的直接子目录中。

### 5. 验证 Docker 配置

```bash
python -m tir_stitcher -c config.yaml --dry-run
```

如果看到 "Docker not found"，按第 3 步设置 `docker_path`。

---


## 处理时间参考

| 图像数量 | 阶段①-④ (提取+转换) | 阶段⑤ (ODM 拼接) | 总计 |
|---------|---------------------|-------------------|------|
| 30 张 | ~2 分钟 | ~5-10 分钟 | ~10-15 分钟 |
| 100 张 | ~5 分钟 | ~15-25 分钟 | ~20-30 分钟 |
| 448 张 | ~15 分钟 | ~50-70 分钟 | ~1-1.5 小时 |

> 使用 CPU 处理。GPU 会更快。ODM 阶段的时间受图像重叠度和特征丰富度影响较大。

---

## ODM 拼接原理

[OpenDroneMap](https://www.opendronemap.org/)（ODM）是开源航拍图像拼接引擎，在阶段⑤中自动完成：

1. **特征点检测与匹配** — 用 SIFT 算法找出相邻照片的共同特征点（SIFT 对热红外低对比度纹理效果最好）
2. **运动恢复结构（SfM）** — 根据特征点匹配关系重建三维相机姿态和稀疏点云
3. **密集重建** — 生成稠密点云和 DSM（数字表面模型）
4. **正射校正** — 将图像投影为垂直俯瞰视角，拼接成正射镶嵌图

已为热红外图像预配置了 ODM 参数：

| 参数 | 值 | 作用 |
|------|-----|------|
| `--feature-type` | sift | SIFT 算法更适合热红外低纹理场景 |
| `--radiometric-calibration` | none | 保留原始温度数值，不做 RGB 转换 |
| `--primary-band` | 1 | 仅处理单一温度波段 |
| `--use-exif` | — | 使用 TIF 文件内嵌的 GPS 坐标定位 |
| `--gps-accuracy` | 10 | 民用 GPS 典型精度 (米) |

> Docker 安装和配置详见 [Docker 与 ODM 环境配置](#docker-与-odm-环境配置) 章节。

---

## 断点续传

每个阶段完成后会在项目文件夹生成 `.tir_stitcher_xxx.done` 标记文件，下次运行自动跳过。

**重跑某个阶段：** 删除对应的 `.done` 文件后重新运行。

| 重跑... | 删除... |
|---------|---------|
| 提取 RAW | `.tir_stitcher_extract_raw.done` |
| RAW → TIF | `.tir_stitcher_raw_to_tif.done` |
| 复制 EXIF | `.tir_stitcher_copy_exif.done` |
| 准备 images | `.tir_stitcher_prepare_images.done` |
| 运行 ODM | `.tir_stitcher_run_odm.done` |
| 后处理 | `.tir_stitcher_postprocess.done` |

---

## 配置速查

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `tsdk.distance` | 5.0 | 飞行高度 (米) |
| `tsdk.emissivity` | 0.95 | 地表发射率 |
| `odm.docker_path` | null | Docker 路径 (Windows 用户常需设置) |
| `odm.feature_quality` | high | 特征质量 (ultra/high/medium/low) |
| `odm.min_num_features` | 3000 | 最小特征点数 (热红外建议 2000-4000) |
| `odm.use_gpu` | false | GPU 加速 |
| `pipeline.resume` | true | 断点续传 |
| `pipeline.stop_on_stage_failure` | false | 失败即停 |

完整配置项及中文注释见 `config.yaml`。

---

## 常见问题

| 现象 | 排查方向 |
|------|----------|
| `dji_irp.exe not found` | 在 `tsdk.exe_path` 填 SDK 的 bin 目录路径 |
| `exiftool not found` | 在 `copy_exif.exiftool_path` 填 exiftool 路径 |
| `Docker not found` | 设置 `odm.docker_path` 或在 CMD/PowerShell 中运行 |
| `Need at least 3 images` | ODM 至少需要 3 张重叠照片才能拼接 |
| RAW 尺寸不对 | 手动设置 `raw_to_tif.rows` 和 `cols`（DJI M3T: 512x640）|
| 拼接失败 / 黑屏 | 降低 `odm.min_num_features` 到 2000-3000 |
| 所有 TIF GPS 坐标相同 | v1.0 已知 bug，v2 已修复（逐对复制，不再批量） |

---

## License

MIT License — see [LICENSE](LICENSE) file for details.
