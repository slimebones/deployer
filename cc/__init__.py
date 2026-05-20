import configparser
import json
import os
import random
import struct
import subprocess
import sys
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Generic, Self, Sequence, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from cyberpas_server.codes import model_validation_error

_PROJECT_CFG = "project.cfg"
encoding = "utf-8"
CodePack = tuple[int, bytes]

_project_root: Path
_user_path: Path
_config: configparser.ConfigParser
_log_configured = False

log = logger


class Model(BaseModel):
    def to_bytes(self) -> bytes:
        return json_to_bytes(self.model_dump())

    @classmethod
    def from_bytes(cls, d: bytes) -> Self:
        return bytes_to_model(cls, d)

    @classmethod
    def from_record(cls, r: Any) -> Self:
        raise NotImplementedError


class ArbitraryModel(Model):
    class Config:
        arbitrary_types_allowed = True


ArbModel = ArbitraryModel


TBaseModel = TypeVar("TBaseModel", bound=BaseModel)
TModel = TypeVar("TModel", bound=Model)
TArbitraryModel = TypeVar("TArbitraryModel", bound=ArbitraryModel)


class CodeError(Exception):
    """
    All custom errors in our systems are represented by this base class. The main feature is the combination of code and message, which is crucial for network interactions as defined by our standards..
    """
    def __init__(self, code: int = 1, *args):
        if code == 0:
            raise Exception("CodeError code cannot be OK")
        super().__init__(code, *args)
        self.code = code
        self.message = "; ".join([str(x) for x in args])

    def __str__(self) -> str:
        return f"{self.__class__.__name__} #{self.code}: {self.message or '*empty message*'}"


def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for start in (here, *here.parents):
        if (start / _PROJECT_CFG).is_file():
            return start
    cwd = Path.cwd()
    for start in (cwd, *cwd.parents):
        if (start / _PROJECT_CFG).is_file():
            return start
    raise RuntimeError(f"Cannot find {_PROJECT_CFG} (searched from package location and cwd)")


def _read_project_id(root: Path) -> str:
    cfg = configparser.ConfigParser()
    cfg.read(root / _PROJECT_CFG, encoding="utf-8")
    return cfg.get("project", "id")


def _parse_rotation(rotation_str: str) -> str:
    rotation_str = rotation_str.strip()
    suffix = rotation_str[-2:].upper()
    if suffix in ("MB", "KB"):
        return f"{rotation_str[:-2].strip()} {suffix}"
    return rotation_str


def _console_log_level() -> str:
    try:
        from cyberpas_server import build

        return "DEBUG" if build.debug else "INFO"
    except ImportError:
        return "INFO"


def _configure_logging() -> None:
    global _log_configured
    if _log_configured:
        return

    rotation = _parse_rotation(_config.get("log", "rotation", fallback="10MB"))
    retention_raw = _config.get("log", "retention", fallback="10")
    try:
        retention: str | int = int(retention_raw)
    except ValueError:
        retention = retention_raw
    log_file = _user_path / "logs" / "main.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level=_console_log_level(), enqueue=True)
    logger.add(
        str(log_file),
        level="DEBUG",
        serialize=True,
        rotation=rotation,
        retention=retention,
        compression="gz",
        enqueue=True,
        encoding="utf-8",
    )
    _log_configured = True


def _bootstrap() -> None:
    global _project_root, _user_path, _config

    _project_root = _find_project_root()
    project_id = _read_project_id(_project_root)

    homedir = Path.home()
    if os.name == "nt":
        _user_path = Path(homedir, "AppData", "Roaming", project_id)
    else:
        _user_path = Path(homedir, "." + project_id)
    _user_path.mkdir(parents=True, exist_ok=True)

    user_cfg = _user_path / "user.cfg"
    user_cfg.touch(exist_ok=True)

    _config = configparser.ConfigParser()
    _config.read(user_cfg, encoding="utf-8")
    _configure_logging()


def cwd(p: str | Path) -> Path:
    return Path(Path.cwd(), p)


def user(p: str | Path) -> Path:
    # @todo disallow path outs
    return Path(_user_path, p)


def source(p: str | Path) -> Path:
    return Path(_project_root, p)


def project_root() -> Path:
    return _project_root


def bytes_to_model(model_type: type[TModel], input: bytes) -> TModel:
    try:
        return model_type.model_validate(bytes_to_json(input))
    except ValidationError as e:
        raise CodeError(model_validation_error) from e


def convert_enums(data: Any) -> Any:
    if isinstance(data, dict):
        new = {}
        for k, v in data.items():
            new[k] = _convert_enums_v(v)
        return new
    elif isinstance(data, (list, tuple, set)):
        r = []
        for x in data:
            r.append(convert_enums(x))
        return r
    else:
        return data


def _convert_enums_v(v: Any) -> Any:
    final_v = v
    if isinstance(v, Enum):
        final_v = v.value
    elif isinstance(v, dict):
        final_v = convert_enums(v)
    elif isinstance(v, (list, tuple, set)):
        final_v = []
        for x in v:
            final_v.append(_convert_enums_v(x))
    return final_v


def bytes_to_string(input: bytes) -> str:
    return input.decode(encoding)


def string_to_bytes(input: str) -> bytes:
    return input.encode(encoding)


def models_to_bytes(models: Sequence[BaseModel]) -> bytes:
    return json.dumps([x.model_dump() for x in models]).encode(encoding)


def model_to_bytes(model: BaseModel) -> bytes:
    return model.model_dump_json().encode(encoding)


def json_to_bytes(input: Any) -> bytes:
    return json.dumps(convert_enums(input)).encode(encoding)


def bytes_to_json(input: bytes) -> Any:
    if input == bytes():
        return {}
    return json.loads(input.decode(encoding))


def float_to_bytes(input: float) -> bytes:
    return struct.pack("<f", input)


def bytes_to_float(input: bytes) -> float:
    return struct.unpack("<f", input)[0]


def int_to_bytes(input: int, size: int, signed: bool) -> bytes:
    return input.to_bytes(size, byteorder="little", signed=signed)


def bytes_to_int(input: bytes, signed: bool) -> int:
    return int.from_bytes(input, byteorder="little", signed=signed)


def adaptively_to_bytes(input: Any, signed: bool):
    if isinstance(input, str):
        return string_to_bytes(input)
    elif isinstance(input, int):
        return int_to_bytes(input, 8, signed)
    elif isinstance(input, bytes):
        return input
    else:
        raise TypeError("Unsupported data type")


def unwrap_coded_structure(input: bytes) -> tuple[int, bytes]:
    """
    Unwraps bytes structure consisting of 2 leading bytes of integer code, and rest of the bytes as payload.

    Returns tuple of code and payload.
    """
    if len(input) < 2:
        raise Exception("too short coded structure")
    code = struct.unpack("<H", input[:2])[0]
    payload = bytes()
    if len(input) > 2:
        payload = input[2:]
    return code, payload


class Reader:
    def __init__(self, b: bytes):
        self.i = 0
        self.b = b

    def read(self, size: int) -> bytes:
        r = self.b[self.i:self.i+size]
        self.i += size
        if len(r) == 0:
            raise StopIteration
        return r

    def read_int(self, size: int, signed: bool) -> int:
        return bytes_to_int(self.read(size), signed)

    def read_string(self, size: int) -> str:
        return bytes_to_string(self.read(size))


class Vector2:
    def __init__(self, x: float, y: float):
        self.x: float = x
        self.y: float = y


T = TypeVar("T")
class Signal(Generic[T]):
    def __init__(self):
        self._listeners = []

    def connect(self, listener: Callable[[T], Awaitable[None]]):
        """Connect a listener to this signal."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def disconnect(self, listener: Callable[[T], Awaitable[None]]):
        """Disconnect a listener from this signal."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, value: T):
        """Emit the signal, calling all connected listeners."""
        for listener in self._listeners:
            await listener(value)


def call(command: str, dir: os.PathLike | str | None = None) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=dir,
        )
        return (result.stdout, result.stderr, result.returncode)
    except subprocess.CalledProcessError as e:
        return (e.stdout, e.stderr, e.returncode)


def makeid() -> str:
    """Creates unique id.

    Returns:
        Id created.
    """
    return uuid.uuid4().hex


def random_float(min: float, max: float) -> float:
    return random.uniform(min, max)


def random_float_rounded(min: float, max: float, r: int) -> float:
    return round(random_float(min, max), r)


def random_vector2(v1: Vector2, v2: Vector2) -> Vector2:
    x = random_float(v1.x, v2.x)
    y = random_float(v1.y, v2.y)
    return Vector2(x, y)

def random_vector2_from_float_lists(min: list[float], max: list[float]) -> Vector2:
    min_vector = Vector2(min[0], min[1])
    max_vector = Vector2(max[0], max[1])
    return random_vector2(min_vector, max_vector)


def config_get(section: str, key: str, default: str = "") -> str:
    return _config.get(section, key, fallback=default)


_bootstrap()
