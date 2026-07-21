"""Slice 01 — shared storage: LocalDiskStorage (TDD checklist #9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mparlament.shared.storage import LocalDiskStorage

pytestmark = pytest.mark.anyio


async def test_local_disk_storage_saves_and_paths(tmp_path: Path) -> None:
    storage = LocalDiskStorage(base_dir=tmp_path)

    public_path = await storage.save("resolutions", "uchwala.docx", b"hello")

    assert public_path == "/uploads/resolutions/uchwala.docx"
    on_disk = tmp_path / "resolutions" / "uchwala.docx"
    assert on_disk.exists()
    assert on_disk.read_bytes() == b"hello"
    assert storage.path_for("resolutions", "uchwala.docx") == public_path


async def test_local_disk_storage_sanitizes_traversal(tmp_path: Path) -> None:
    storage = LocalDiskStorage(base_dir=tmp_path)

    public_path = await storage.save("resolutions", "../../etc/passwd", b"x")

    # The written file must stay inside base_dir/resolutions.
    written = (tmp_path / "resolutions").glob("**/*")
    files = [p for p in written if p.is_file()]
    assert len(files) == 1
    assert tmp_path in files[0].resolve().parents
    assert ".." not in public_path


async def test_local_disk_storage_dedupes_collisions(tmp_path: Path) -> None:
    storage = LocalDiskStorage(base_dir=tmp_path)

    first = await storage.save("attachments", "file.pdf", b"a")
    second = await storage.save("attachments", "file.pdf", b"b")

    assert first == "/uploads/attachments/file.pdf"
    assert first != second
    assert (tmp_path / "attachments" / "file.pdf").read_bytes() == b"a"
    # second landed under a distinct name, original untouched.
    assert (tmp_path / Path(second.removeprefix("/uploads/"))).read_bytes() == b"b"
