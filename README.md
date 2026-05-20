# Deployer

`deployer` is a deployment-oriented CLI.

## Installation

### Normal install (use as a CLI)

Install from PyPI:

```bash
python -m pip install deployer
```

Then verify:

```bash
deployer version
```

### Editable install (for local development)

Clone the repository, then install in editable mode from the project root:

```bash
python -m pip install -e .
```

Then verify:

```bash
deployer version
```

## CLI

```bash
deployer run [-d] [-m MODE] [-t TARGET_DIR] [ARGS...] [--KEY VALUE ...]
deployer run-all [-d] [-m MODE] [-t TARGET_DIR] [ARGS...] [--KEY VALUE ...]
deployer version [-d] [-m MODE]
```

- `TARGET_DIR` defaults to current directory.
- Extra positional values are passed to `deploy.py::main(*args, **kwargs)`.
- Extra `--key value` pairs are passed as keyword arguments.
- `run-all` executes for the target directory and nested directories that also contain both `project.cfg` and `deploy.py`.

## Required Files

### `project.cfg`

```cfg
[project]
id = company-name.project-name
name = Human readable project name
version = 1.0.0
```

- `id` must contain exactly two kebab-case lowercase parts: `company.project`.
- `name` is the deployed project’s display name; `deployer.sdk.project().name` exposes it to `deploy.py` scripts.
- `version` is the deployed project’s version string (read into `deployer.sdk.project().version`); it is not the `deployer` CLI tool version.

### `deploy.py`

```python
async def main(*args, **kwargs) -> None:
    ...
```

The `main` function must be async and accept both `*args` and `**kwargs`.

## SDK

Use:

```python
import deployer.sdk as sdk
```

This currently maps to the existing SDK implementation while the project transitions from `dome` to `deployer`.

