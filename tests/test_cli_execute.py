from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOME_MAIN = REPO_ROOT / "dome" / "main.py"


def run_dome(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DOME_MAIN), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def write_project(project_dir: Path, project_id: str) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "module_a").mkdir(parents=True, exist_ok=True)
    (project_dir / "module_a" / "__init__.py").write_text("", encoding="utf-8")
    (project_dir / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (project_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_dir / "code.txt").write_text("sample_code\n", encoding="utf-8")
    (project_dir / "project.py").write_text(
        f"""
from dome import sdk

project_id = "{project_id}"

async def build():
    sdk.init_build()
    sdk.generate_build_info("build.py")
    sdk.generate_codes("codes.py")
    sdk.include_python()
""".strip()
        + "\n",
        encoding="utf-8",
    )


def assert_standard_build_output(project_dir: Path) -> None:
    build_dir = project_dir / "build"
    assert build_dir.exists()
    assert (build_dir / "requirements.txt").exists()
    assert (build_dir / "build.py").exists()
    assert (build_dir / "codes.py").exists()
    assert (build_dir / "module_a").exists()
    assert (build_dir / "module_a" / "__init__.py").exists()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    write_project(tmp_path, "project-root")
    return tmp_path


def test_execute_build_for_single_project(workspace: Path) -> None:
    result = run_dome(["-v", "0.1.0", "execute", "build"], cwd=workspace)
    assert result.returncode == 0, result.stderr or result.stdout
    assert_standard_build_output(workspace)


def test_execute_build_for_all_projects(workspace: Path) -> None:
    child_project = workspace / "nested_project"
    write_project(child_project, "project-child")

    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True, capture_output=True)

    result = run_dome(["-v", "0.1.0", "execute", "-a", "build"], cwd=workspace)
    assert result.returncode == 0, result.stderr or result.stdout

    assert_standard_build_output(workspace)
    assert_standard_build_output(child_project)
