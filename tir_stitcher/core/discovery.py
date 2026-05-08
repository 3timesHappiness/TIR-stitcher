"""Project folder discovery for the pipeline."""

from pathlib import Path


def discover_projects(
    workspace: Path,
    filters: list[str],
    case_sensitive: bool = False,
    max_depth: int = 2,
    require_images: bool = True,
) -> list[Path]:
    """Scan *workspace* up to *max_depth* and return matching project folder paths.

    A folder matches if its basename contains ALL strings in *filters* (AND logic).
    """
    results = []
    stack = [(workspace, 0)]

    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            continue

        try:
            entries = sorted(current.iterdir())
            for entry in entries:
                if not entry.is_dir():
                    continue
                name = entry.name
                name_check = name if case_sensitive else name.upper()
                filters_check = [f if case_sensitive else f.upper() for f in filters]

                if all(f in name_check for f in filters_check):
                    results.append(entry)
                elif depth < max_depth:
                    # Only recurse if the folder doesn't already match
                    pass

                # Always recurse down for nested projects
                if depth < max_depth:
                    stack.append((entry, depth + 1))
        except PermissionError:
            continue

    # Re-scan to catch all projects including those nested
    all_dirs = []
    for dirpath, dirnames, _ in _walk_with_depth(workspace, max_depth):
        for d in dirnames:
            full = Path(dirpath) / d
            name_check = d if case_sensitive else d.upper()
            filters_check = [f if case_sensitive else f.upper() for f in filters]
            if all(f in name_check for f in filters_check):
                if full not in all_dirs:
                    all_dirs.append(full)

    if not all_dirs:
        all_dirs = results

    # Filter: require T.JPG files at project root
    if require_images:
        filtered = []
        for p in all_dirs:
            try:
                has_tjpg = any(
                    f.is_file() and "T.JPG" in f.name.upper()
                    for f in p.iterdir()
                )
                if has_tjpg:
                    filtered.append(p)
            except PermissionError:
                continue
        all_dirs = filtered

    return sorted(set(all_dirs), key=lambda p: p.name)


def _walk_with_depth(root: Path, max_depth: int):
    """os.walk limited by depth."""
    import os
    root_depth = len(str(root).split(os.sep))
    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = len(str(dirpath).split(os.sep)) - root_depth
        if current_depth > max_depth:
            dirnames.clear()
            continue
        yield dirpath, dirnames, filenames


def discover_t_jpg_files(project_dir: Path) -> list[Path]:
    """Return sorted list of T.JPG files at the project root (non-recursive)."""
    files = [
        p for p in project_dir.iterdir()
        if p.is_file() and "T.JPG" in p.name.upper()
    ]
    return sorted(files)
