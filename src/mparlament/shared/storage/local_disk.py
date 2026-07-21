"""File storage port + local-disk adapter (CONVENTIONS C14).

Used by resolutions (#19 docx) and votings (#15 attachments). Files live under
``settings.upload_dir/<subdir>/`` and are served publicly at ``/uploads/<subdir>/<name>``
(the FE fallback path). The adapter sanitizes filenames to prevent path traversal and
de-duplicates on collision so an upload never clobbers an existing file.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol, runtime_checkable

from mparlament.shared.config import get_settings

_PUBLIC_ROOT = "/uploads"


@runtime_checkable
class FileStorage(Protocol):
    """Port for persisting uploaded bytes and resolving their public path."""

    async def save(self, subdir: str, filename: str, data: bytes) -> str: ...

    def path_for(self, subdir: str, filename: str) -> str: ...


class LocalDiskStorage:
    """Writes uploads under ``base_dir`` (defaults to ``settings.upload_dir``)."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else get_settings().upload_dir

    def path_for(self, subdir: str, filename: str) -> str:
        return f"{_PUBLIC_ROOT}/{subdir}/{filename}"

    async def save(self, subdir: str, filename: str, data: bytes) -> str:
        return await asyncio.to_thread(self._save_sync, subdir, filename, data)

    def _save_sync(self, subdir: str, filename: str, data: bytes) -> str:
        safe_name = self._sanitize(filename)
        directory = self.base_dir / subdir
        directory.mkdir(parents=True, exist_ok=True)
        target = self._dedupe(directory, safe_name)
        target.write_bytes(data)
        return self.path_for(subdir, target.name)

    @staticmethod
    def _sanitize(filename: str) -> str:
        # Drop any directory components (defeats ../ and absolute paths).
        name = Path(filename).name
        return name or "upload"

    @staticmethod
    def _dedupe(directory: Path, name: str) -> Path:
        target = directory / name
        if not target.exists():
            return target
        stem, suffix = Path(name).stem, Path(name).suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
