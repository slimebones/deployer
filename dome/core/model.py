from typing import Self

from pydantic import BaseModel

from dome import core

__all__ = [
    "Model",
    "ArbModel",
]


class Model(BaseModel):
    def to_bytes(self) -> bytes:
        return core.json_to_bytes(self.model_dump())

    @classmethod
    def from_bytes(cls, d: bytes) -> Self:
        return core.bytes_to_model(cls, d)


class ArbModel(Model):
    class Config:
        arbitrary_types_allowed = True

