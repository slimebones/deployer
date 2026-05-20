"""Host: local shell and persistent SSH execution."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tarfile
from contextvars import ContextVar
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING

from installer.sdk._recycle import send_to_recycle

if TYPE_CHECKING:
    import paramiko

_host_context: ContextVar[Host | None] = ContextVar("host_context", default=None)

_LOCAL: Host | None = None


def _quote(path: Path | str) -> str:
    return shlex.quote(str(path).replace("\\", "/"))


class Host:
    """
    Run commands and file operations on this machine (local) or a remote host (SSH).

    Use :meth:`local` for the current machine and construct ``Host(hostname, user=...)``
    for remotes. While a remote instance is alive, one SSH session is kept open.
    """

    def __init__(
        self,
        hostname: str,
        *,
        user: str | None = None,
        port: int = 22,
        connect_timeout: float = 30.0,
    ) -> None:
        self._hostname = hostname
        self._user = user
        self._port = port
        self._connect_timeout = connect_timeout
        self._is_local = False
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self._remote_platform: str | None = None

    @classmethod
    def local(cls) -> Host:
        global _LOCAL
        if _LOCAL is None:
            inst = object.__new__(cls)
            inst._is_local = True
            inst._hostname = "localhost"
            inst._user = None
            inst._port = 0
            inst._connect_timeout = 0.0
            inst._client = None
            inst._sftp = None
            inst._remote_platform = None
            _LOCAL = inst
        return _LOCAL

    @classmethod
    def current(cls) -> Host:
        host = _host_context.get()
        if host is None:
            return cls.local()
        return host

    def __enter__(self) -> Host:
        self._context_token = _host_context.set(self)
        return self

    def __exit__(self, *exc: object) -> None:
        _host_context.reset(self._context_token)
        if not self._is_local:
            self.close()

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _label(self) -> str:
        if self._is_local:
            return "localhost"
        user = self._user or os.environ.get("USER", os.environ.get("USERNAME", ""))
        if user:
            return f"{user}@{self._hostname}"
        return self._hostname

    def _log(self, message: str) -> None:
        print(f"[host {self._label()}] {message}")

    def _resolve_path(self, path: PathLike | str, *, base: Path | None = None) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        if base is None:
            from installer.sdk import project

            base = project().source_dir
        return Path(base, p)

    def _ensure_ssh(self) -> paramiko.SSHClient:
        if self._is_local:
            raise RuntimeError("SSH is not used for the local host.")
        if self._client is not None:
            return self._client

        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict = {
            "hostname": self._hostname,
            "port": self._port,
            "timeout": self._connect_timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }
        if self._user:
            kwargs["username"] = self._user
        client.connect(**kwargs)
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        self._client = client
        return client

    def _ensure_sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            self._sftp = self._ensure_ssh().open_sftp()
        return self._sftp

    def _platform(self) -> str:
        if self._is_local:
            return sys.platform
        if self._remote_platform is not None:
            return self._remote_platform
        retcode, stdout, _ = self._execute_raw("uname -s 2>/dev/null || echo Windows_NT")
        if retcode != 0:
            self._remote_platform = "win32"
            return self._remote_platform
        name = stdout.strip()
        if name == "Windows_NT" or name.lower().startswith("mingw") or name.lower().startswith("msys"):
            self._remote_platform = "win32"
        elif name == "Darwin":
            self._remote_platform = "darwin"
        else:
            self._remote_platform = "linux"
        return self._remote_platform

    def execute(
        self,
        command: str,
        *,
        cwd: PathLike | str | None = None,
        background: bool = False,
    ) -> tuple[str, str]:
        retcode, stdout, stderr = self._execute_raw(command, cwd=cwd, background=background)
        if retcode != 0:
            raise RuntimeError(
                f"command failed (exit {retcode}): '{command}'\n{stderr}"
            )
        return stdout, stderr

    def _execute_raw(
        self,
        command: str,
        *,
        cwd: PathLike | str | None = None,
        background: bool = False,
    ) -> tuple[int, str, str]:
        cwd_str = str(cwd) if cwd is not None else None
        msg = f"execute '{command}'"
        if background:
            msg += ", background"
        if cwd_str:
            msg += f", cwd '{cwd_str}'"
        self._log(msg)

        if self._is_local:
            return self._execute_local(command, cwd=cwd_str, background=background)
        return self._execute_ssh(command, cwd=cwd_str, background=background)

    def _execute_local(
        self,
        command: str,
        *,
        cwd: str | None,
        background: bool,
    ) -> tuple[int, str, str]:
        if cwd is None:
            from installer.sdk import project

            cwd = str(project().source_dir)
        if background:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return 0, "", ""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", str(e)

    def _execute_ssh(
        self,
        command: str,
        *,
        cwd: str | None,
        background: bool,
    ) -> tuple[int, str, str]:
        client = self._ensure_ssh()
        if cwd:
            command = f"cd {_quote(cwd)} && {command}"
        if background:
            command = f"nohup {command} >/dev/null 2>&1 </dev/null &"
        _stdin, stdout, stderr = client.exec_command(command)
        retcode = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        return retcode, out, err

    def mkdir(
        self,
        path: PathLike | str,
        *,
        parents: bool = True,
        exist_ok: bool = False,
    ) -> None:
        resolved = self._resolve_path(path)
        self._log(f"mkdir '{resolved}'")
        if self._is_local:
            resolved.mkdir(parents=parents, exist_ok=exist_ok)
            return

        platform = self._platform()
        q = _quote(resolved.as_posix())
        if platform == "win32":
            cmd = (
                f'powershell -NoProfile -Command "New-Item -ItemType Directory -Force '
                f'-Path \'{resolved}\' | Out-Null"'
            )
        else:
            flags = ["-p"] if parents else []
            cmd = f"mkdir {' '.join(flags)} {q}".strip()
        retcode, _, stderr = self._execute_raw(cmd)
        if retcode != 0 and not exist_ok:
            raise RuntimeError(f"mkdir failed for '{resolved}': {stderr}")

    def copy(
        self,
        src: PathLike | str,
        dest: PathLike | str,
        *,
        recursive: bool = True,
    ) -> None:
        from installer.sdk import project

        src_path = Path(src)
        dest_path = Path(dest)
        local_src = self._resolve_path(src) if not src_path.is_absolute() else src_path

        if self._is_local:
            dest_resolved = self._resolve_path(dest)
            self._log(f"copy '{local_src}' -> '{dest_resolved}'")
            if local_src.is_dir():
                if recursive:
                    shutil.copytree(local_src, dest_resolved, dirs_exist_ok=True)
                else:
                    raise IsADirectoryError(f"source '{local_src}' is a directory; set recursive=True")
            else:
                dest_resolved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_src, dest_resolved)
            return

        project_root = project().source_dir.resolve()
        try:
            local_src.resolve().relative_to(project_root)
            upload_from_project = local_src.exists()
        except ValueError:
            upload_from_project = False
        if upload_from_project:
            remote_dest = dest_path.as_posix() if dest_path.is_absolute() else dest_path.as_posix()
            self._log(f"upload '{local_src}' -> '{remote_dest}'")
            sftp = self._ensure_sftp()
            if local_src.is_dir():
                self._sftp_put_tree(sftp, local_src, remote_dest)
            else:
                self._sftp_mkdir_parents(sftp, remote_dest)
                sftp.put(str(local_src), remote_dest)
            return

        src_remote = src_path.as_posix() if src_path.is_absolute() else self._resolve_path(src).as_posix()
        dest_remote = dest_path.as_posix() if dest_path.is_absolute() else Path(dest).as_posix()
        self._log(f"copy '{src_remote}' -> '{dest_remote}'")
        platform = self._platform()
        if platform == "win32":
            flag = "-Recurse" if recursive else ""
            cmd = f'Copy-Item -Path "{src_remote}" -Destination "{dest_remote}" {flag} -Force'
            cmd = f"powershell -NoProfile -Command {shlex.quote(cmd)}"
        else:
            flag = "-r" if recursive else ""
            cmd = f"cp {flag} {_quote(src_remote)} {_quote(dest_remote)}"
        self.execute(cmd)

    def _sftp_mkdir_parents(self, sftp: paramiko.SFTPClient, remote_path: str) -> None:
        parent = os.path.dirname(remote_path.replace("\\", "/"))
        if not parent or parent == "/":
            return
        parts: list[str] = []
        for part in parent.split("/"):
            if not part:
                continue
            parts.append(part)
            path = "/" + "/".join(parts)
            try:
                sftp.stat(path)
            except OSError:
                try:
                    sftp.mkdir(path)
                except OSError:
                    pass

    def _sftp_put_tree(self, sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str) -> None:
        remote_dir = remote_dir.replace("\\", "/").rstrip("/")
        try:
            sftp.stat(remote_dir)
        except OSError:
            sftp.mkdir(remote_dir)
        for root, dirs, files in os.walk(local_dir):
            rel = Path(root).relative_to(local_dir)
            remote_root = remote_dir if rel == Path(".") else f"{remote_dir}/{rel.as_posix()}"
            for d in dirs:
                path = f"{remote_root}/{d}"
                try:
                    sftp.stat(path)
                except OSError:
                    sftp.mkdir(path)
            for f in files:
                local_file = Path(root, f)
                remote_file = f"{remote_root}/{f}"
                sftp.put(str(local_file), remote_file)

    def move(self, src: PathLike | str, dest: PathLike | str) -> None:
        src_resolved = self._resolve_path(src)
        dest_resolved = self._resolve_path(dest)
        self._log(f"move '{src_resolved}' -> '{dest_resolved}'")
        if self._is_local:
            dest_resolved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_resolved), str(dest_resolved))
            return

        platform = self._platform()
        if platform == "win32":
            cmd = f'Move-Item -Path "{src_resolved}" -Destination "{dest_resolved}" -Force'
            cmd = f"powershell -NoProfile -Command {shlex.quote(cmd)}"
        else:
            cmd = f"mv {_quote(src_resolved.as_posix())} {_quote(dest_resolved.as_posix())}"
        self.execute(cmd)

    def recycle(self, *paths: PathLike | str) -> None:
        if not paths:
            return
        for path in paths:
            target = self._resolve_path(path).resolve()
            self._log(f"recycle '{target}'")
            if self._is_local:
                send_to_recycle(target)
            else:
                self._remote_recycle(target)

    def _remote_recycle(self, path: Path) -> None:
        platform = self._platform()
        q = _quote(path.as_posix())
        if platform == "win32":
            script = (
                f'Add-Type -AssemblyName Microsoft.VisualBasic; '
                f'[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("{path}", "OnlyErrorDialogs", "SendToRecycleBin")'
            )
            self.execute(f"powershell -NoProfile -Command {shlex.quote(script)}")
        elif platform == "darwin":
            escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
            self.execute(f'osascript -e \'tell application "Finder" to delete POSIX file "{escaped}"\'')
        else:
            for cmd in (
                f"gio trash {q}",
                f"trash-put {q}",
                f"kioclient5 move {q} trash:/",
            ):
                retcode, _, _ = self._execute_raw(cmd)
                if retcode == 0:
                    return
            self.execute(f"rm -rf {q}")

    def remove(self, *paths: PathLike | str) -> None:
        if not paths:
            return
        resolved = [self._resolve_path(p) for p in paths]
        quoted = " ".join(_quote(p.as_posix()) for p in resolved)
        self._log(f"remove {quoted}")
        if self._is_local:
            if sys.platform == "win32":
                for p in resolved:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    elif p.exists():
                        p.unlink()
            else:
                self.execute(f"rm -rf {quoted}")
            return

        platform = self._platform()
        if platform == "win32":
            for p in resolved:
                flag = "-Recurse -Force" if p.is_dir() or "*" in str(p) else "-Force"
                self.execute(f'Remove-Item -Path "{p}" {flag}')
        else:
            self.execute(f"rm -rf {quoted}")

    def tar(
        self,
        source: PathLike | str,
        archive: PathLike | str,
        *,
        gzip: bool = True,
    ) -> None:
        source_resolved = self._resolve_path(source)
        archive_resolved = self._resolve_path(archive)
        self._log(f"tar '{source_resolved}' -> '{archive_resolved}'")
        if self._is_local:
            mode = "w:gz" if gzip else "w"
            with tarfile.open(archive_resolved, mode) as tar:
                tar.add(source_resolved, arcname=source_resolved.name)
            return

        ext = ".tar.gz" if gzip else ".tar"
        if not str(archive_resolved).endswith(ext) and gzip:
            archive_resolved = Path(str(archive_resolved) + ".gz" if not str(archive_resolved).endswith(".gz") else archive_resolved)
        z = "z" if gzip else ""
        self.execute(
            f"tar -c{z}f {_quote(archive_resolved.as_posix())} -C {_quote(source_resolved.parent.as_posix())} {_quote(source_resolved.name)}"
        )

    def zip(self, source: PathLike | str, archive: PathLike | str) -> None:
        source_resolved = self._resolve_path(source)
        archive_resolved = self._resolve_path(archive)
        if not str(archive_resolved).endswith(".zip"):
            archive_resolved = Path(str(archive_resolved) + ".zip")
        self._log(f"zip '{source_resolved}' -> '{archive_resolved}'")
        if self._is_local:
            if sys.platform == "win32":
                shutil.make_archive(
                    str(archive_resolved.with_suffix("")),
                    "zip",
                    root_dir=str(source_resolved.parent),
                    base_dir=source_resolved.name,
                )
            else:
                parent = source_resolved.parent
                self.execute(
                    f"zip -r {_quote(archive_resolved.as_posix())} {_quote(source_resolved.name)}",
                    cwd=str(parent),
                )
            return

        platform = self._platform()
        if platform == "win32":
            self.execute(
                f'Compress-Archive -Path "{source_resolved}" -DestinationPath "{archive_resolved}" -Force'
            )
        else:
            parent = source_resolved.parent
            self.execute(
                f"zip -r {_quote(archive_resolved.as_posix())} {_quote(source_resolved.name)}",
                cwd=str(parent.as_posix()),
            )
