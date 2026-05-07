from __future__ import annotations

import os
from collections import Counter
from typing import Literal

from rich import print
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table

from .constants import MIME_TYPE_ICONS, colormap
from .mime import get_mime_type
from .utils import get_gitignore_matcher

GroupBy = Literal["mime", "extension"] | None
SortBy = Literal["name", "size", "date"] | None


# ── Collection ──────────────────────────────────────────────────────────────────

def _scan_dir(
    root: str,
    base: str,
    matcher,
    recursive: bool,
    files_out: list[os.DirEntry],
    dirs_out: list[os.DirEntry] | None,
    top_level_only: bool,
) -> None:
    try:
        entries = list(os.scandir(root))
    except PermissionError:
        if root == base:
            raise
        return  # silently skip inaccessible subdirectories

    for entry in entries:
        is_dir = entry.is_dir(follow_symlinks=False)
        rel = os.path.relpath(entry.path, base) + ("/" if is_dir else "")
        if matcher and matcher.match_file(rel):
            continue

        if is_dir:
            if dirs_out is not None and (not top_level_only or root == base):
                dirs_out.append(entry)
            if recursive:
                _scan_dir(entry.path, base, matcher, recursive, files_out, dirs_out, top_level_only)
        else:
            files_out.append(entry)


def _collect(
    path: str,
    *,
    recursive: bool = False,
    gitignore: bool = False,
    collect_dirs: bool = False,
) -> tuple[list[os.DirEntry], list[os.DirEntry]]:
    """
    Return (files, dirs).

    When collect_dirs=True and recursive=False: top-level directories only.
    When collect_dirs=True and recursive=True: all directories at every depth.
    """
    matcher = get_gitignore_matcher(path) if gitignore else None
    files: list[os.DirEntry] = []
    dirs: list[os.DirEntry] = []
    _scan_dir(
        path, path, matcher, recursive, files,
        dirs if collect_dirs else None,
        top_level_only=not recursive,
    )
    return files, dirs


# ── Filtering ────────────────────────────────────────────────────────────────────

def _apply_filters(
    entries: list[os.DirEntry],
    *,
    mime_type: str | None = None,
    extension: str | None = None,
    text: str | None = None,
) -> list[os.DirEntry]:
    if mime_type:
        entries = [e for e in entries if get_mime_type(e.path) == mime_type]
    if extension:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        entries = [e for e in entries if os.path.splitext(e.name)[1].lower() == ext]
    if text:
        needle = text.lower()
        entries = [e for e in entries if needle in e.name.lower()]
    return entries


# ── Sorting ──────────────────────────────────────────────────────────────────────

def _sort_entries(entries: list[os.DirEntry], sort_by: SortBy) -> list[os.DirEntry]:
    if sort_by == "size":
        return sorted(entries, key=lambda e: e.stat().st_size)
    if sort_by == "date":
        return sorted(entries, key=lambda e: e.stat().st_mtime)
    if sort_by == "name":
        return sorted(entries, key=lambda e: e.name.lower())
    return entries


# ── Display: count ───────────────────────────────────────────────────────────────

def _display_count_flat(files: list[os.DirEntry], dirs: list[os.DirEntry]) -> None:
    print(f"Directories: {len(dirs)}")
    print(f"Files: {len(files)}")


def _display_count_grouped(entries: list[os.DirEntry], group_by: str) -> None:
    if group_by == "mime":
        counts: Counter[str] = Counter(
            get_mime_type(e.path) or "Unknown MIME Type" for e in entries
        )
        title, col_label = "File Counts by MIME Type", "MIME Type"
    else:
        counts = Counter(
            os.path.splitext(e.name)[1].lower() or "No Extension" for e in entries
        )
        title, col_label = "File Counts by Extension", "Extension"

    table = Table(
        show_header=True,
        header_style="bold magenta",
        title=title,
        title_style="bold underline magenta",
    )
    table.add_column(col_label, style="bold red", justify="left")
    table.add_column("Count", style="bold yellow", justify="right")
    for key, count in counts.most_common():
        table.add_row(key, str(count))
    print(table)


# ── Display: flat listing ────────────────────────────────────────────────────────

def _display_flat_list(
    files: list[os.DirEntry], dirs: list[os.DirEntry], path: str
) -> None:
    """Side-by-side directories/files table — the default view."""
    dir_names = [f"{e.name}/" for e in dirs]
    file_names = [e.name for e in files]
    max_len = max(len(dir_names), len(file_names), 1)
    dir_names += [""] * (max_len - len(dir_names))
    file_names += [""] * (max_len - len(file_names))

    label = path if path != "." else "CWD"
    table = Table(
        show_header=True,
        header_style="bold magenta",
        title=f"{label} Listing",
        title_style="bold underline magenta",
    )
    table.add_column("Index", style="dim", width=6, justify="right")
    table.add_column("Directories", style="bold blue underline", justify="left")
    table.add_column("Files", style="bold green underline", justify="left")
    for i, (d, f) in enumerate(zip(dir_names, file_names), start=1):
        table.add_row(str(i), d, f)
    print(table)


def _display_file_list(files: list[os.DirEntry], path: str) -> None:
    """Flat indexed path list — used when filters or --recursive are active."""
    label = path if path != "." else "CWD"
    table = Table(
        show_header=True,
        header_style="bold magenta",
        title=f"{label} Listing",
        title_style="bold underline magenta",
    )
    table.add_column("Index", style="dim", width=6, justify="right")
    table.add_column("Path", style="bold cyan", justify="left")
    for i, entry in enumerate(files, start=1):
        table.add_row(str(i), entry.path)
    print(table)


# ── Display: grouped ─────────────────────────────────────────────────────────────

def _display_grouped_mime(files: list[os.DirEntry]) -> None:
    groups: dict[str, list[str]] = {}
    for entry in files:
        mime = get_mime_type(entry.path) or "unknown/type"
        groups.setdefault(mime, []).append(entry.name)

    panels = []
    for mime, names in groups.items():
        prefix, _, suffix = mime.partition("/")
        color = colormap.get(prefix, colormap.get(suffix, "white"))
        icon = MIME_TYPE_ICONS.get(suffix, MIME_TYPE_ICONS.get(prefix, "📁"))
        content = "\n".join(f"[{color}]{n}[/{color}]" for n in names)
        panels.append(
            Panel(content, title=f"{icon} {mime} ({len(names)})", border_style=color, expand=False)
        )
    print(Columns(panels))


def _display_grouped_extension(files: list[os.DirEntry], path: str) -> None:
    groups: dict[str, list[str]] = {}
    for entry in files:
        ext = os.path.splitext(entry.name)[1].lower() or "No Extension"
        groups.setdefault(ext, []).append(entry.path)

    label = path if path != "." else "CWD"
    table = Table(
        show_header=True,
        header_style="bold magenta",
        title=f"{label} Files Grouped by Extension",
        title_style="bold underline magenta",
    )
    table.add_column("Index", style="dim", width=6, justify="center")
    table.add_column("Extension", style="bold red", justify="left")
    table.add_column("Files", style="bold yellow", justify="left")
    for ext, paths in groups.items():
        for i, fp in enumerate(paths, start=1):
            table.add_row(str(i), ext if i == 1 else "", fp)
        table.add_row("")  # blank separator between extension groups
    print(table)


# ── Public entry point ───────────────────────────────────────────────────────────

def run(
    path: str = ".",
    *,
    count: bool = False,
    group_by: GroupBy = None,
    filter_mime: str | None = None,
    filter_ext: str | None = None,
    filter_text: str | None = None,
    sort_by: SortBy = None,
    recursive: bool = False,
    gitignore: bool = False,
) -> None:
    """
    Unified listing entry point. All flags compose freely:
    --recursive, --count, --group-by, --filter-*, and --sort work in any combination.
    """
    has_filters = bool(filter_mime or filter_ext or filter_text)

    # Dirs are needed for the default side-by-side view and for flat count.
    # In recursive mode, collect ALL dirs (not just top-level).
    needs_dirs = (not recursive and not has_filters and not group_by) or (count and not group_by)

    try:
        files, dirs = _collect(
            path,
            recursive=recursive,
            gitignore=gitignore,
            collect_dirs=needs_dirs,
        )
    except FileNotFoundError:
        print(f"[bold yellow]Error:[/bold yellow] The directory '{path}' does not exist.")
        return
    except PermissionError:
        print(f"[bold yellow]Error:[/bold yellow] You do not have permission to access '{path}'.")
        return

    if has_filters:
        files = _apply_filters(files, mime_type=filter_mime, extension=filter_ext, text=filter_text)

    if sort_by:
        files = _sort_entries(files, sort_by)

    # Dispatch to the appropriate display function
    if count:
        if group_by:
            _display_count_grouped(files, group_by)
        else:
            _display_count_flat(files, dirs)
    elif group_by == "mime":
        _display_grouped_mime(files)
    elif group_by == "extension":
        _display_grouped_extension(files, path)
    elif recursive or has_filters:
        _display_file_list(files, path)
    else:
        _display_flat_list(files, dirs, path)
