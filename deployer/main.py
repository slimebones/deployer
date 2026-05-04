from __future__ import annotations

import argparse
import asyncio
import configparser
import importlib.util
import inspect
import os
import re
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

__version__ = "1.2.0"

PROJECT_ID_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$"
)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deployer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-d", "--debug", action="store_true", default=False)
    common.add_argument("-m", "--mode", default="default")

    run_parser = subparsers.add_parser("run", parents=[common])
    run_parser.add_argument("-t", "--target", default=".")
    run_all_parser = subparsers.add_parser("run-all", parents=[common])
    run_all_parser.add_argument("-t", "--target", default=".")

    subparsers.add_parser("version", parents=[common])
    return parser


def _parse_extra_tokens(tokens: list[str]) -> tuple[list[str], dict[str, str | bool]]:
    args: list[str] = []
    kwargs: dict[str, str | bool] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:]
            if not key:
                raise ValueError("empty keyword name is not allowed")
            key = key.replace("-", "_")
            next_i = i + 1
            if next_i < len(tokens) and not tokens[next_i].startswith("--"):
                kwargs[key] = tokens[next_i]
                i += 2
            else:
                kwargs[key] = True
                i += 1
            continue
        args.append(token)
        i += 1
    return args, kwargs


def _load_project_config(target_dir: Path) -> str:
    cfg_path = target_dir / "project.cfg"
    if not cfg_path.exists():
        raise FileNotFoundError(f"project config is not found: '{cfg_path}'")

    parser = configparser.ConfigParser()
    parser.read(cfg_path, encoding="utf-8")

    if "project" not in parser:
        raise ValueError("project.cfg must contain [project] section")
    project_id = parser["project"].get("id", "").strip()
    if not project_id:
        raise ValueError("project.cfg must define [project].id")
    if PROJECT_ID_PATTERN.fullmatch(project_id) is None:
        raise ValueError(
            "project id must follow 'companyname.projectname' with both names in kebab-case lowercase"
        )
    return project_id


def _load_deploy_module(target_dir: Path) -> ModuleType:
    deploy_path = target_dir / "deploy.py"
    if not deploy_path.exists():
        raise FileNotFoundError(f"deploy entrypoint is not found: '{deploy_path}'")

    spec = importlib.util.spec_from_file_location("deployer_target", deploy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from '{deploy_path}'")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_main(module: ModuleType):
    main = getattr(module, "main", None)
    if main is None:
        raise ValueError("deploy.py must define `main(*args, **kwargs)`")
    if not inspect.iscoroutinefunction(main):
        raise TypeError("deploy.py:main must be async")

    signature = inspect.signature(main)
    has_varargs = any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in signature.parameters.values()
    )
    has_varkw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
    )
    if not has_varargs or not has_varkw:
        raise TypeError("deploy.py:main signature must be async def main(*args, **kwargs)")
    return main


async def _run() -> None:
    parser = _build_cli_parser()
    parsed, extra = parser.parse_known_args()

    if parsed.command == "version":
        print(__version__)
        return

    if parsed.command in {"run", "run-all"}:
        target_dir = Path(parsed.target).resolve()
        if not target_dir.is_dir():
            raise NotADirectoryError(f"target directory does not exist: '{target_dir}'")

        args, kwargs = _parse_extra_tokens(extra)
        run_all = parsed.command == "run-all"
        for project_dir in _resolve_targets(target_dir, run_all):
            _load_project_config(project_dir)
            module = _load_deploy_module(project_dir)
            main = _resolve_main(module)
            old_cwd = Path.cwd()
            try:
                # Execute each deploy.py from its own project directory.
                # This matches expectation for relative file operations in deploy scripts.
                os.chdir(project_dir)
                await main(*args, **kwargs)
            finally:
                os.chdir(old_cwd)
        return

    raise ValueError(f"unknown command '{parsed.command}'")


def _resolve_targets(target_dir: Path, run_all: bool) -> list[Path]:
    if not run_all:
        return [target_dir]

    targets: list[Path] = []
    for candidate in sorted([target_dir, *target_dir.rglob("*")]):
        if not candidate.is_dir():
            continue
        if (candidate / "project.cfg").exists() and (candidate / "deploy.py").exists():
            targets.append(candidate)
    return targets


def main() -> None:
    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()

