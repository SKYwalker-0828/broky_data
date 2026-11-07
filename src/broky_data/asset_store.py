"""Local, content-addressed asset storage adapter for the M01 prototype."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
from typing import BinaryIO, Protocol


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_CHUNK_SIZE = 1024 * 1024


class AssetStoreError(RuntimeError):
    """Base error for local asset storage failures."""


class AssetIntegrityError(AssetStoreError):
    """Raised when a stored object is unsafe or fails integrity checks."""


@dataclass(frozen=True)
class AssetRef:
    """Opaque M01 reference, represented only by a lowercase SHA-256 digest."""

    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.sha256, str) or not _DIGEST_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be exactly 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class AssetReceipt:
    """Write result; this is not a canonical RelicWeave Asset record."""

    ref: AssetRef
    size_bytes: int


class AssetStore(Protocol):
    """Replaceable byte-store contract; it does not define business metadata."""

    def put_bytes(self, data: bytes) -> AssetReceipt: ...

    def put_stream(self, source: BinaryIO) -> AssetReceipt: ...

    def open(self, ref: AssetRef) -> BinaryIO: ...

    def exists(self, ref: AssetRef) -> bool: ...

    def verify(self, ref: AssetRef) -> bool: ...


class LocalAssetStore:
    """Store immutable blobs under a caller-managed local directory.

    The root must be writable and trusted. This adapter provides no application-level
    authorization, encryption, backup, provenance metadata, or deletion workflow.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve()

    def put_bytes(self, data: bytes) -> AssetReceipt:
        """Store bytes and return their content reference and byte count."""
        return self.put_stream(io.BytesIO(data))

    def put_stream(self, source: BinaryIO) -> AssetReceipt:
        """Stream an object into storage without loading the whole object in memory."""
        staging = self._ensure_layout()
        fd, temporary_name = tempfile.mkstemp(prefix="asset-", dir=staging)
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        size_bytes = 0

        try:
            with os.fdopen(fd, "wb") as temporary:
                while True:
                    block = source.read(_CHUNK_SIZE)
                    if block == b"":
                        break
                    if not isinstance(block, (bytes, bytearray, memoryview)):
                        raise TypeError("source.read() must return bytes")
                    block = bytes(block)
                    temporary.write(block)
                    digest.update(block)
                    size_bytes += len(block)
                temporary.flush()
                os.fsync(temporary.fileno())

            ref = AssetRef(digest.hexdigest())
            destination = self._object_path(ref, create_parent=True)
            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                if not self.verify(ref):
                    raise AssetIntegrityError(
                        f"existing object does not match its SHA-256 reference: {ref.sha256}"
                    )
            except OSError as exc:
                raise AssetStoreError(
                    "could not atomically publish the asset; the filesystem must support "
                    "same-filesystem hard links"
                ) from exc
            return AssetReceipt(ref=ref, size_bytes=size_bytes)
        finally:
            temporary_path.unlink(missing_ok=True)

    def open(self, ref: AssetRef) -> BinaryIO:
        """Open a stored object for reading; callers may use verify() before use."""
        path = self._object_path(ref, create_parent=False)
        if path is None:
            raise FileNotFoundError(f"asset not found: {ref.sha256}")
        if path.is_symlink():
            raise AssetIntegrityError(f"asset path is not a regular file: {ref.sha256}")
        if not path.exists():
            raise FileNotFoundError(f"asset not found: {ref.sha256}")
        if not path.is_file():
            raise AssetIntegrityError(f"asset path is not a regular file: {ref.sha256}")
        return path.open("rb")

    def exists(self, ref: AssetRef) -> bool:
        """Return whether a regular object exists for this reference."""
        path = self._object_path(ref, create_parent=False)
        if path is None:
            return False
        if path.is_symlink():
            raise AssetIntegrityError(f"asset path is not a regular file: {ref.sha256}")
        if not path.exists():
            return False
        if not path.is_file():
            raise AssetIntegrityError(f"asset path is not a regular file: {ref.sha256}")
        return True

    def verify(self, ref: AssetRef) -> bool:
        """Recompute and compare the stored object's SHA-256 digest."""
        digest = hashlib.sha256()
        with self.open(ref) as stored:
            for block in iter(lambda: stored.read(_CHUNK_SIZE), b""):
                digest.update(block)
        return digest.hexdigest() == ref.sha256

    def _ensure_layout(self) -> Path:
        self._ensure_directory(self.root)
        staging = self.root / ".staging"
        self._ensure_directory(staging)
        return staging

    def _object_path(self, ref: AssetRef, *, create_parent: bool) -> Path | None:
        if not isinstance(ref, AssetRef):
            raise TypeError("ref must be an AssetRef")

        if create_parent:
            self._ensure_directory(self.root / "sha256")
            shard = self.root / "sha256" / ref.sha256[:2]
            self._ensure_directory(shard)
            return shard / ref.sha256[2:]

        if not self.root.exists():
            return None
        self._require_directory(self.root)
        bucket = self.root / "sha256"
        if not bucket.exists():
            if bucket.is_symlink():
                raise AssetIntegrityError("sha256 storage directory must not be a symlink")
            return None
        self._require_directory(bucket)
        shard = bucket / ref.sha256[:2]
        if not shard.exists():
            if shard.is_symlink():
                raise AssetIntegrityError("asset shard must not be a symlink")
            return None
        self._require_directory(shard)
        return shard / ref.sha256[2:]

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        if path.is_symlink():
            raise AssetIntegrityError(f"storage directory must not be a symlink: {path}")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        LocalAssetStore._require_directory(path)
        if os.name == "posix":
            path.chmod(0o700)

    @staticmethod
    def _require_directory(path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise AssetIntegrityError(f"storage path is not a real directory: {path}")
