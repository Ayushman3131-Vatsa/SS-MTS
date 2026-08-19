import os
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import BusinessRuleError
from app.modules.task_management.domain import errors


class LocalAttachmentStorage:
    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def resolve(self, storage_key: str) -> Path:
        if not storage_key or any(part in {"", ".", ".."} for part in storage_key.split("/")):
            raise ValueError("Invalid attachment storage key")
        candidate = (self._root / Path(*storage_key.split("/"))).resolve()
        if self._root not in candidate.parents:
            raise ValueError("Attachment storage key escaped the configured root")
        return candidate

    async def save(self, storage_key: str, upload: UploadFile, *, max_bytes: int) -> int:
        destination = self.resolve(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        size = 0
        try:
            with temporary.open("xb") as handle:
                while chunk := await upload.read(64 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise BusinessRuleError(
                            f"Attachment exceeds the {max_bytes}-byte limit",
                            code=errors.ATTACHMENT_SIZE,
                        )
                    handle.write(chunk)
            os.replace(temporary, destination)
            return size
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    async def delete(self, storage_key: str) -> None:
        self.resolve(storage_key).unlink(missing_ok=True)

