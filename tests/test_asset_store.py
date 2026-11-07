import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from broky_data import AssetIntegrityError, AssetRef, LocalAssetStore


class FailingStream:
    def __init__(self) -> None:
        self.read_count = 0

    def read(self, size: int = -1) -> bytes:
        self.read_count += 1
        if self.read_count == 1:
            return b"partial asset"
        raise OSError("simulated input failure")


class LocalAssetStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "assets"
        self.store = LocalAssetStore(self.root)

    def test_put_is_content_addressed_and_deduplicated(self) -> None:
        payload = b"artifact bytes"
        first = self.store.put_bytes(payload)
        second = self.store.put_bytes(payload)

        self.assertEqual(first, second)
        self.assertEqual(first.ref.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(first.size_bytes, len(payload))
        self.assertTrue(self.store.exists(first.ref))
        self.assertTrue(self.store.verify(first.ref))
        with self.store.open(first.ref) as stored:
            self.assertEqual(stored.read(), payload)

    def test_stream_write_does_not_modify_source(self) -> None:
        source = io.BytesIO(b"streamed content")
        receipt = self.store.put_stream(source)

        self.assertEqual(source.getvalue(), b"streamed content")
        self.assertEqual(source.tell(), len(b"streamed content"))
        self.assertTrue(self.store.verify(receipt.ref))

    def test_large_stream_round_trips_across_chunks(self) -> None:
        payload = bytes(range(256)) * 9000
        receipt = self.store.put_stream(io.BytesIO(payload))

        self.assertEqual(receipt.size_bytes, len(payload))
        with self.store.open(receipt.ref) as stored:
            self.assertEqual(stored.read(), payload)

    def test_tampering_is_detected(self) -> None:
        receipt = self.store.put_bytes(b"original")
        object_path = self.root / "sha256" / receipt.ref.sha256[:2] / receipt.ref.sha256[2:]
        object_path.write_bytes(b"changed")

        self.assertTrue(self.store.exists(receipt.ref))
        self.assertFalse(self.store.verify(receipt.ref))

    def test_put_does_not_overwrite_a_corrupted_object(self) -> None:
        receipt = self.store.put_bytes(b"original")
        object_path = self.root / "sha256" / receipt.ref.sha256[:2] / receipt.ref.sha256[2:]
        object_path.write_bytes(b"changed")

        with self.assertRaises(AssetIntegrityError):
            self.store.put_bytes(b"original")
        self.assertEqual(object_path.read_bytes(), b"changed")

    def test_missing_asset_is_not_reported_as_present(self) -> None:
        ref = AssetRef(hashlib.sha256(b"missing").hexdigest())

        self.assertFalse(self.store.exists(ref))
        with self.assertRaises(FileNotFoundError):
            self.store.open(ref)

    def test_invalid_reference_cannot_encode_a_path(self) -> None:
        with self.assertRaises(ValueError):
            AssetRef("../outside")

    def test_failed_stream_does_not_publish_partial_object(self) -> None:
        with self.assertRaisesRegex(OSError, "simulated input failure"):
            self.store.put_stream(FailingStream())  # type: ignore[arg-type]

        staging = self.root / ".staging"
        self.assertEqual(list(staging.iterdir()), [])
        self.assertFalse((self.root / "sha256").exists())

    def test_symlinked_bucket_is_rejected(self) -> None:
        outside = Path(self.tempdir.name) / "outside"
        outside.mkdir()
        self.root.mkdir()
        (self.root / "sha256").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(AssetIntegrityError):
            self.store.put_bytes(b"not written through a symlink")


if __name__ == "__main__":
    unittest.main()
