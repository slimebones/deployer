# Installer SDK

The SDK is used from `install.py` scripts. Import it as:

```python
import installer.sdk as sdk
```

The CLI sets the active project before `main()` runs, so `sdk.project()` and `sdk.Host.current()` are always available inside `install.py`.

## Layout

The SDK has three areas:

| Area | Purpose | Examples |
|------|---------|----------|
| **Information** | Read the active deployment target | `project()` |
| **Build** | Prepare artifacts under the project build directory | `init_build()`, `include()`, `generate_build_info()` |
| **Host** | Run commands and file operations on a machine | `Host.local()`, `Host.current()`, remote `Host(...)` |

---

## Information

### `project() -> Project`

Returns the active `Project` model for the target being deployed.

Common fields:

- `id`, `version`, `name`, `debug`, `mode`
- `source_dir` — project root (where `project.cfg` and sources live)
- `build_dir` — output directory for this run (under the project tree)

---

## Build

Build helpers only touch paths under the current project’s `source_dir` / `build_dir`. They do not use `Host`.

### `init_build()`

Deletes and recreates `project().build_dir`.

### `include(target, dest=None)`

Copies files or directories from `source_dir` into `build_dir`.

- Relative `target` paths are resolved from `source_dir`.
- Glob patterns (`*`, `?`, `[`) copy every match, preserving paths relative to the source root; `dest` must not be set for globs.

### `include_python()`

Convenience: includes top-level `*.py`, `requirements.txt`, and packages that have `__init__.py` directly under `source_dir`.

### `generate_build_info(target)`

Writes a small version/id/time module at `target` (`.py`, `.js`, or `.ts`).

---

## Host

All shell and filesystem work goes through `Host`. There are no top-level `call`, `recycle`, or `rm` helpers anymore.

### Local vs remote

| | Local | Remote |
|---|--------|--------|
| Instance | `Host.local()` or `Host.current()` (default) | `Host("hostname", user="deploy")` |
| Commands | Native shell (`subprocess`) | Persistent **SSH** (one session per instance) |
| Paths | Relative paths → `project().source_dir` | Relative paths → `project().source_dir` for uploads; otherwise paths are on the remote machine |

```python
# Default: this machine
sdk.Host.current().execute("echo hello")

# Same as current when no context override
sdk.Host.local().mkdir("dist")

# Remote (SSH; connection stays open until close() or context exit)
with sdk.Host("prod.example.com", user="deploy") as host:
    host.execute("systemctl restart myapp")
    host.copy("build/app.tar.gz", "/opt/app/app.tar.gz")
```

Use `with host:` to set `Host.current()` for nested calls and to close the SSH session when leaving the block.

### `execute(command, *, cwd=None, background=False) -> (stdout, stderr)`

Runs a shell command and returns captured output. Raises if the command exits non-zero.

- **Local:** `cwd` defaults to `project().source_dir`.
- **Remote:** `cwd` is a path on the remote host.
- **background:** fire-and-forget (local: detached process; remote: `nohup ... &`); returns empty strings on success.

### File helpers

Paths are resolved like `execute` (relative → project `source_dir` on the machine where the operation runs; for remote **upload**, sources under the local project tree are sent via SFTP).

| Method | Description |
|--------|-------------|
| `mkdir(path, *, parents=True, exist_ok=False)` | Create directory |
| `copy(src, dest, *, recursive=False)` | Copy or upload (`copy` from project tree → remote uses SFTP) |
| `move(src, dest)` | Move/rename |
| `recycle(*paths)` | Move to OS trash / recycle bin |
| `remove(*paths)` | Permanent delete |
| `tar(source, archive, *, gzip=True)` | Create `.tar` / `.tar.gz` |
| `zip(source, archive)` | Create `.zip` |

Platform-specific tools are chosen automatically (e.g. trash APIs on Windows, `gio trash` / `zip` / `tar` on Linux, PowerShell on Windows remotes).

### SSH requirements (remote)

- OpenSSH server on the target
- Authentication via SSH agent and/or keys in `~/.ssh` (standard `paramiko` behavior)
- Optional: `user=` in the constructor; port defaults to `22`

Close long-lived remotes explicitly if not using a context manager:

```python
host = sdk.Host("db.internal", user="ops")
try:
    host.execute("pg_dump mydb > /tmp/backup.sql")
finally:
    host.close()
```

---

## Typical `install.py`

```python
import installer.sdk as sdk


async def main(*args, **kwargs) -> None:
    p = sdk.project()
    sdk.init_build()
    sdk.include("src/**")
    sdk.generate_build_info("src/build_info.py")

    host = sdk.Host.current()
    host.execute(f"cd {p.build_dir} && ./package.sh")

    with sdk.Host("deploy.example.com", user="ci") as remote:
        remote.mkdir("/var/www/myapp", parents=True)
        remote.copy(p.build_dir / "release.tar.gz", "/var/www/myapp/release.tar.gz")
        remote.execute("tar -xzf /var/www/myapp/release.tar.gz -C /var/www/myapp")
```

---

## Types exported from `installer.sdk`

- `Project`, `Model` — project model types
- `Host` — command and filesystem access
- `project`, `init_build`, `include`, `include_python`, `generate_build_info` — build/information API
