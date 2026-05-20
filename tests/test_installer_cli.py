from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_MAIN = REPO_ROOT / "installer" / "main.py"


def _project_cfg(
    project_id: str = "company-name.project-name",
    *,
    name: str = "Test Project",
    version: str = "0.1.0",
) -> str:
    return f"[project]\nid = {project_id}\nname = {name}\nversion = {version}\n"


def run_installer(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER_MAIN), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_runs_install_main_with_args_and_kwargs(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("result.txt").write_text(f"{args}|{kwargs}", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run", "hello", "--mykwargs", "123"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "('hello',)|{'mykwargs': '123'}"


def test_requires_valid_project_id(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(
        _project_cfg("CompanyName.project-name"),
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        "async def main(*args, **kwargs):\n    return None\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "kebab-case lowercase" in result.stderr


def test_requires_project_name(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(
        "[project]\nid = company-name.project-name\nversion = 1.0.0\n",
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        "async def main(*args, **kwargs):\n    return None\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "[project].name" in result.stderr


def test_requires_project_version(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(
        "[project]\nid = company-name.project-name\nname = My App\n",
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        "async def main(*args, **kwargs):\n    return None\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "[project].version" in result.stderr


def test_requires_async_main_signature(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "install.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "main(*args, **kwargs)" in result.stderr


def test_version_command_outputs_version(tmp_path: Path) -> None:
    result = run_installer(["version"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.2.0"


def test_run_all_executes_nested_projects(tmp_path: Path) -> None:
    root = tmp_path
    child = tmp_path / "nested"
    child.mkdir()

    (root / "project.cfg").write_text(
        _project_cfg("company.root", name="Root", version="1.0.0"),
        encoding="utf-8",
    )
    (child / "project.cfg").write_text(
        _project_cfg("company.child", name="Child", version="2.0.0"),
        encoding="utf-8",
    )

    (root / "install.py").write_text(
        """
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("ran.txt").write_text("root", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (child / "install.py").write_text(
        """
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("ran.txt").write_text("child", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run-all"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (root / "ran.txt").read_text(encoding="utf-8") == "root"
    assert (child / "ran.txt").read_text(encoding="utf-8") == "child"


def test_run_does_not_execute_nested_projects(tmp_path: Path) -> None:
    root = tmp_path
    child = tmp_path / "nested"
    child.mkdir()

    (root / "project.cfg").write_text(
        _project_cfg("company.root", name="Root", version="1.0.0"),
        encoding="utf-8",
    )
    (child / "project.cfg").write_text(
        _project_cfg("company.child", name="Child", version="2.0.0"),
        encoding="utf-8",
    )

    (root / "install.py").write_text(
        """
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("ran.txt").write_text("root", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (child / "install.py").write_text(
        """
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("ran.txt").write_text("child", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (root / "ran.txt").read_text(encoding="utf-8") == "root"
    assert not (child / "ran.txt").exists()


def test_sdk_project_context_is_available(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("project-id.txt").write_text(sdk.project().id, encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "project-id.txt").read_text(encoding="utf-8") == "company-name.project-name"


def test_sdk_project_name_from_cfg(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(
        _project_cfg(name="My Deployed App", version="3.2.1"),
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk
from pathlib import Path

async def main(*args, **kwargs) -> None:
    p = sdk.project()
    Path("meta.txt").write_text(f"{p.name}|{p.version}", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "meta.txt").read_text(encoding="utf-8") == "My Deployed App|3.2.1"


def test_global_flags_before_command_are_applied(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(
        _project_cfg(version="5.8.0"),
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk
from pathlib import Path

async def main(*args, **kwargs) -> None:
    p = sdk.project()
    Path("context.txt").write_text(f"{p.version}|{p.debug}|{p.mode}", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["-d", "-m", "prod", "run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "context.txt").read_text(encoding="utf-8") == "5.8.0|True|prod"


def test_user_code_errors_show_full_traceback(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
async def main(*args, **kwargs) -> None:
    raise RuntimeError("boom")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "Traceback (most recent call last)" in result.stderr
    assert "RuntimeError: boom" in result.stderr


def test_loads_dotenv_for_target_project(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / ".env").write_text(
        "MY_SECRET=hello\n",
        encoding="utf-8",
    )
    (tmp_path / "install.py").write_text(
        """
import os
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("env.txt").write_text(os.getenv("MY_SECRET", ""), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "env.txt").read_text(encoding="utf-8") == "hello"


def test_dotenv_isolated_between_run_all_projects(tmp_path: Path) -> None:
    root = tmp_path
    child = tmp_path / "nested"
    child.mkdir()

    (root / "project.cfg").write_text(
        _project_cfg("company.root", name="Root", version="1.0.0"),
        encoding="utf-8",
    )
    (child / "project.cfg").write_text(
        _project_cfg("company.child", name="Child", version="2.0.0"),
        encoding="utf-8",
    )
    (root / ".env").write_text("SHARED_KEY=root-value\n", encoding="utf-8")

    (root / "install.py").write_text(
        """
import os
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("env.txt").write_text(os.getenv("SHARED_KEY", ""), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (child / "install.py").write_text(
        """
import os
from pathlib import Path

async def main(*args, **kwargs) -> None:
    Path("env.txt").write_text(os.getenv("SHARED_KEY", ""), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run-all"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (root / "env.txt").read_text(encoding="utf-8") == "root-value"
    assert (child / "env.txt").read_text(encoding="utf-8") == ""


def test_sdk_include_glob_copies_matching_files(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("c", encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk

async def main(*args, **kwargs) -> None:
    sdk.init_build()
    sdk.include("*.txt")
    sdk.include("sub/*.txt")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    build = tmp_path / "build"
    assert (build / "a.txt").read_text(encoding="utf-8") == "a"
    assert (build / "sub" / "c.txt").read_text(encoding="utf-8") == "c"
    assert not (build / "b.md").exists()


def test_sdk_include_glob_with_dest_raises(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk

async def main(*args, **kwargs) -> None:
    sdk.init_build()
    sdk.include("*.txt", dest="out")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "glob pattern" in result.stderr and "dest" in result.stderr


def test_sdk_include_glob_no_matches_raises(tmp_path: Path) -> None:
    (tmp_path / "project.cfg").write_text(_project_cfg(), encoding="utf-8")
    (tmp_path / "install.py").write_text(
        """
import installer.sdk as sdk

async def main(*args, **kwargs) -> None:
    sdk.init_build()
    sdk.include("*.nomatch")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = run_installer(["run"], cwd=tmp_path)
    assert result.returncode == 1
    assert "Cannot find include paths matching glob" in result.stderr
