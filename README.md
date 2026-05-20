# Installer

`installer` is a deployment-oriented CLI.

## Installation

### Normal install (use as a CLI)

Install from PyPI:

```bash
python -m pip install installer
```

Then verify:

```bash
installer version
```

### Editable install (for local development)

Clone the repository, then install in editable mode from the project root:

```bash
python -m pip install -e .
```

Then verify:

```bash
installer version
```

## CLI

```bash
installer run [-d] [-m MODE] [-t TARGET_DIR] [ARGS...] [--KEY VALUE ...]
installer run-all [-d] [-m MODE] [-t TARGET_DIR] [ARGS...] [--KEY VALUE ...]
installer version [-d] [-m MODE]
```

- `TARGET_DIR` defaults to current directory.
- Extra positional values are passed to `install.py::main(*args, **kwargs)`.
- Extra `--key value` pairs are passed as keyword arguments.
- `run-all` executes for the target directory and nested directories that also contain both `project.cfg` and `install.py`.

## Required Files

### `project.cfg`

```cfg
[project]
id = company-name.project-name
version = 1.0.0
```

- `id` must contain exactly two kebab-case lowercase parts: `company.project`.
- `name` is the directory that contains `project.cfg`; `installer.sdk.project().name` exposes it to `install.py` scripts.
- `version` is the deployed project’s version string (read into `installer.sdk.project().version`); it is not the `installer` CLI tool version.

### `install.py`

```python
async def main(*args, **kwargs) -> None:
    ...
```

The `main` function must be async and accept both `*args` and `**kwargs`.

## SDK

Use:

```python
import installer.sdk as sdk
```
