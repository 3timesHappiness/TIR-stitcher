"""Cross-platform utility functions."""

import os
import shutil
import subprocess
from pathlib import Path


def run_command(
    cmd: list[str],
    timeout: int | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a command as a list (never shell=True). Raises CalledProcessError on failure."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
    )


def find_executable(
    name: str,
    search_paths: list[Path] | None = None,
    search_recursive: bool = False,
) -> Path | None:
    """Locate an executable by name. Checks search_paths, then system PATH, then rglob."""
    # On Windows, try with .exe suffix
    candidates = [name]
    if os.name == "nt" and not name.endswith(".exe"):
        candidates.append(f"{name}.exe")

    # 1. Explicit search paths
    if search_paths:
        for sp in search_paths:
            if not sp.exists():
                continue
            for c in candidates:
                p = sp / c
                if p.is_file():
                    return p

    # 2. System PATH
    for c in candidates:
        found = shutil.which(c)
        if found:
            return Path(found)

    # 3. Recursive search
    if search_recursive and search_paths:
        for sp in search_paths:
            if not sp.exists():
                continue
            try:
                for p in sp.rglob(name):
                    if p.is_file():
                        return p
            except (PermissionError, OSError):
                continue
            for c in candidates:
                try:
                    for p in sp.rglob(c):
                        if p.is_file():
                            return p
                except (PermissionError, OSError):
                    continue

    return None


def auto_detect_dimensions(raw_path: Path, channels: int = 1) -> tuple[int, int]:
    """Infer (rows, cols) from a .raw file's size. Tries common DJI resolutions first."""
    file_size = raw_path.stat().st_size
    total_pixels = file_size // (channels * 2)  # uint16 = 2 bytes

    if file_size % (channels * 2) != 0:
        raise ValueError(
            f"File size {file_size} not divisible by channels*2={channels * 2} "
            f"for {raw_path}"
        )

    # Common DJI thermal resolutions
    common = [(512, 640), (640, 512), (480, 640), (640, 480)]
    for r, c in common:
        if r * c == total_pixels:
            return (r, c)

    # Fall back to square or factor pairs
    import math
    side = int(math.isqrt(total_pixels))
    for h in range(side, 0, -1):
        if total_pixels % h == 0:
            w = total_pixels // h
            if w >= h:
                return (h, w)

    raise ValueError(f"Cannot infer dimensions for {total_pixels} pixels in {raw_path}")


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def stamp_path(project_dir: Path, stage_name: str) -> Path:
    """Return the stamp file path for a stage in a project."""
    return project_dir / f".tir_stitcher_{stage_name}.done"


def is_stage_done(project_dir: Path, stage_name: str) -> bool:
    """Check if a stage has already completed for this project."""
    return stamp_path(project_dir, stage_name).exists()


def mark_stage_done(project_dir: Path, stage_name: str) -> None:
    """Create a stamp file marking the stage as complete."""
    stamp_path(project_dir, stage_name).touch()


def clear_stage_stamp(project_dir: Path, stage_name: str) -> None:
    """Remove a stage stamp file so the stage will re-run."""
    sp = stamp_path(project_dir, stage_name)
    if sp.exists():
        sp.unlink()
