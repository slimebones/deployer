from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from installer.sdk._recycle import send_to_recycle

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_MAIN = REPO_ROOT / "installer" / "main.py"


def _project_cfg() -> str:
    return "[project]\nid = company-name.project-name\nversion = 1.0.0\n"


def run_installer(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER_MAIN), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_send_to_recycle_removes_file(tmp_path: Path) -> None:
    victim = tmp_path / "discard-me.txt"
    victim.write_text("bye", encoding="utf-8")
    send_to_recycle(victim)
    assert not victim.exists()


def test_send_to_recycle_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        send_to_recycle(tmp_path / "nope.txt")


def test_trash_via_install_run(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "remove.txt").write_text("x", encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk

async def main(*args, **kwargs) -> None:
    sdk.Host.current().recycle("remove.txt")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "remove.txt").exists()
