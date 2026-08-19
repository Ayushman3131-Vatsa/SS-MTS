from pathlib import Path
from typing import Protocol

from fastapi import UploadFile


class AttachmentStorage(Protocol):
    async def save(self, storage_key: str, upload: UploadFile, *, max_bytes: int) -> int: ...

    def resolve(self, storage_key: str) -> Path: ...

    async def delete(self, storage_key: str) -> None: ...

