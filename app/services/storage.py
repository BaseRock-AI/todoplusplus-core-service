from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    original_filename: str
    content_type: str | None
    size_bytes: int


class StorageProvider(ABC):
    @abstractmethod
    def save_bytes(self, namespace: str, filename: str, data: bytes, content_type: str | None = None) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self, root_dir: str) -> None:
        self.root_path = Path(root_dir).expanduser().resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, namespace: str, filename: str, data: bytes, content_type: str | None = None) -> StoredFile:
        safe_name = filename.replace("/", "_").replace("\\", "_").strip() or "upload.bin"
        storage_key = f"{namespace}/{uuid4().hex}_{safe_name}"
        target_path = self.root_path / storage_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        return StoredFile(
            storage_key=storage_key,
            original_filename=safe_name,
            content_type=content_type,
            size_bytes=len(data),
        )

    def read_bytes(self, storage_key: str) -> bytes:
        return (self.root_path / storage_key).read_bytes()

    def exists(self, storage_key: str) -> bool:
        return (self.root_path / storage_key).exists()

    def delete(self, storage_key: str) -> None:
        target = self.root_path / storage_key
        if target.exists():
            target.unlink()


def build_storage_provider() -> StorageProvider:
    if settings.storage_backend == "local":
        return LocalStorageProvider(settings.storage_local_root)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


storage_provider: StorageProvider = build_storage_provider()
