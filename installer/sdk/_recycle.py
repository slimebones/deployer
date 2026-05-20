"""Send files and directories to the OS recycle bin / trash."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def send_to_recycle(path: Path) -> None:
    """Move ``path`` into the platform recycle bin / trash folder."""
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Cannot trash non-existent path '{resolved}'.")

    system = sys.platform
    if system == "win32":
        _windows_recycle(resolved)
    elif system == "darwin":
        _macos_trash(resolved)
    else:
        _unix_trash(resolved)


def _windows_recycle(path: Path) -> None:
    import ctypes
    from ctypes import Structure, byref, c_void_p, c_wchar_p, windll
    from ctypes.wintypes import BOOL, DWORD, HWND, UINT, WORD

    class SHFILEOPSTRUCTW(Structure):
        _fields_ = [
            ("hwnd", HWND),
            ("wFunc", UINT),
            ("pFrom", c_wchar_p),
            ("pTo", c_wchar_p),
            ("fFlags", WORD),
            ("fAnyOperationsAborted", BOOL),
            ("hNameMappings", c_void_p),
            ("lpszProgressTitle", c_wchar_p),
        ]

    FO_DELETE = 0x0003
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    FOF_NOERRORUI = 0x0400

    # SHFileOperationW expects a double-null-terminated list of paths.
    from_buffer = f"{path}\0\0"
    op = SHFILEOPSTRUCTW(
        hwnd=None,
        wFunc=FO_DELETE,
        pFrom=from_buffer,
        pTo=None,
        fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
        fAnyOperationsAborted=False,
        hNameMappings=None,
        lpszProgressTitle=None,
    )
    result = windll.shell32.SHFileOperationW(byref(op))
    if result != 0:
        raise OSError(f"Windows recycle failed for '{path}' (error {result}).")
    if op.fAnyOperationsAborted:
        raise OSError(f"Windows recycle was aborted for '{path}'.")


def _macos_trash(path: Path) -> None:
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Finder" to delete POSIX file "{escaped}"'
    proc = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise OSError(
            f"macOS trash failed for '{path}'"
            + (f": {detail}" if detail else ".")
        )


def _unix_trash(path: Path) -> None:
    for argv in (
        ["gio", "trash", str(path)],
        ["trash-put", str(path)],
        ["kioclient5", "move", str(path), "trash:/"],
    ):
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            continue
        if proc.returncode == 0:
            return

    _xdg_trash(path)


def _xdg_trash(path: Path) -> None:
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        trash_dir = Path(data_home) / "Trash"
    else:
        trash_dir = Path.home() / ".local" / "share" / "Trash"

    files_dir = trash_dir / "files"
    info_dir = trash_dir / "info"
    files_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)

    dest = files_dir / path.name
    if dest.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = files_dir / f"{path.stem}.{stamp}{path.suffix}"

    if path.is_dir():
        shutil.move(str(path), str(dest))
    else:
        shutil.move(str(path), str(dest))

    info_path = info_dir / f"{dest.name}.trashinfo"
    info_path.write_text(
        "\n".join(
            [
                "[Trash Info]",
                f"Path={path}",
                f"DeletionDate={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
