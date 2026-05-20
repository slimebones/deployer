# core

Shared utilities for Python: project paths, per-user data, configuration, logging, serialization helpers, and small primitives used across packages.

## Import-time initialization

`core` configures itself when the module is first imported. You do **not** need to call `init()` (it is kept only as a backward-compatible no-op).

On import, `core`:

1. Locates the project root by walking upward from the package until it finds `project.cfg` (same directory as `pyproject.toml` for this repo).
2. Reads `project.id` from that file and creates the per-user directory:
  - Windows: `%AppData%\Roaming\<project.id>`
  - Linux/macOS: `~/.<project.id>`
3. Loads `user.cfg` from that directory (created if missing).
4. Configures [loguru](https://github.com/Delgan/loguru) logging (stderr + JSON file sink).

This makes `core` safe in the main process, worker processes, and modules that call `config_get` at import time.

## Paths


| Function         | Description                                   |
| ---------------- | --------------------------------------------- |
| `project_root()` | Directory containing `project.cfg`            |
| `source(p)`      | Path under project root: `project_root() / p` |
| `user(p)`        | Path under the per-user data directory        |
| `cwd(p)`         | Path under the current working directory      |


Example:

```python
from cyberpas_server.core import source, user

cfg = source("project.cfg")
logs = user("logs/main.log")
```

## Configuration

`config_get(section, key, default="")` reads from `user.cfg` in the per-user directory.

```python
from cyberpas_server.core import config_get

host = config_get("postgres", "host", "localhost")
```

Optional keys in `user.cfg` for logging:

```ini
[log]
rotation = 10MB
retention = 10
```

`rotation` uses loguru syntax (`10MB` is normalized to `10 MB`). `retention` is passed to loguru as the file sink retention policy.

## Logging

Import the configured loguru logger as `log`:

```python
from cyberpas_server.core import log

log.info("server started")
log.warning("deprecated option")
log.debug("verbose detail")

try:
    ...
except Exception as e:
    log.opt(exception=e).error("request failed")
```

Sinks:

- **stderr** — human-readable, level `DEBUG` when `cyberpas_server.build.debug` is true, otherwise `INFO`
- `**user("logs/main.log")`** — JSON lines, rotation/compression/retention from `user.cfg`, `enqueue=True` for asyncio, threads, and multiprocessingj

Request-scoped fields (module, client, auth) use loguru’s `contextualize`:

```python
with log.contextualize(module="web", remote_addr=addr):
    log.info("handled request")
```

## Serialization & errors

- `Model` / `ArbitraryModel` — Pydantic models with `to_bytes` / `from_bytes`
- `CodeError` — errors with integer `code` and `message` for the wire protocol
- `bytes_to_json`, `json_to_bytes`, `unwrap_coded_structure`, `Reader`, etc.

## Other helpers

`Signal`, `Vector2`, `makeid()`, `call()`, random helpers, and enum conversion utilities — see `__init__.py`.

## Project layout

`project.cfg` at the server project root:

```ini
[project]
id = almaz.cyberpas-server
name = Cyberpas Server
version = 1.0.0
```

The `id` value determines the per-user folder name and must be unique per deployed application. When using the `deployer` CLI, `name` and `version` are required in `project.cfg` as well.