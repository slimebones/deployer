import argparse
from pathlib import Path
from typing import Callable

from installer.core import Model


class RunArgs(Model):
    args: argparse.Namespace
    cwd: Path
    version: str
    debug: bool
    mode: str
    projectfile: Path
    build_dir: Path
    response: Callable
    source: Path

    class Config:
        arbitrary_types_allowed = True
