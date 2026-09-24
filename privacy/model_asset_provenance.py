"""Signed provenance verification for private model assets."""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
from typing import Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)


MANIFEST_ENV = "GVAI_PRIVATE_MODEL_ASSET_MANIFEST"
PUBLIC_KEY_ENV = "GVAI_PRIVATE_MODEL_ASSET_PUBLIC_KEY"
MANIFEST_SCHEMA = "gvai-private-model-assets-v1"

_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_ASSETS = 4096
_READ_SIZE = 1024 * 1024


class ModelAssetProvenanceError(RuntimeError):
    """Configured model assets could not be authenticated."""


@dataclass(frozen=True)
class VerifiedModelAssets:
    """Authenticated paths and the external trust root used to verify them."""

    manifest_path: Path
    paths: tuple[Path, ...]
    _public_key: bytes = field(repr=False)


def _failure() -> ModelAssetProvenanceError:
    return ModelAssetProvenanceError(
        "private model asset provenance verification failed"
    )


def _decode_base64(value: str, expected_length: int) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise _failure() from None
    if len(decoded) != expected_length:
        raise _failure()
    return decoded


def _object_without_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _canonical_path(raw: str | os.PathLike[str]) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise _failure()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        raise _failure() from None
    if candidate != resolved:
        raise _failure()
    return resolved


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        descriptor = os.open(path, flags)
        status = os.fstat(descriptor)
        opened_path = Path(
            f"/proc/self/fd/{descriptor}"
        ).resolve(strict=True)
    except OSError:
        try:
            os.close(descriptor)
        except (NameError, OSError):
            pass
        raise _failure() from None

    if (
        not stat.S_ISREG(status.st_mode)
        or opened_path != path
        or status.st_nlink != 1
    ):
        os.close(descriptor)
        raise _failure()

    return descriptor, status


def _read_manifest(path: Path) -> Mapping[str, object]:
    descriptor, before = _open_regular(path)
    chunks = []
    total = 0

    try:
        while True:
            chunk = os.read(descriptor, min(_READ_SIZE, 65536))
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_MANIFEST_BYTES:
                raise _failure()
            chunks.append(chunk)

        after = os.fstat(descriptor)
        opened_path = Path(
            f"/proc/self/fd/{descriptor}"
        ).resolve(strict=True)
    except (OSError, ModelAssetProvenanceError):
        raise _failure() from None
    finally:
        os.close(descriptor)

    if _identity(before) != _identity(after) or opened_path != path:
        raise _failure()

    try:
        document = json.loads(
            b"".join(chunks).decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise _failure() from None

    if not isinstance(document, dict):
        raise _failure()
    return document


def _hash_asset(path: Path, expected_size: int) -> str:
    descriptor, before = _open_regular(path)
    digest = hashlib.sha256()
    total = 0

    try:
        while True:
            chunk = os.read(descriptor, _READ_SIZE)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)

        after = os.fstat(descriptor)
        opened_path = Path(
            f"/proc/self/fd/{descriptor}"
        ).resolve(strict=True)
    except OSError:
        raise _failure() from None
    finally:
        os.close(descriptor)

    if (
        total != expected_size
        or before.st_size != expected_size
        or _identity(before) != _identity(after)
        or opened_path != path
    ):
        raise _failure()

    return digest.hexdigest()


def _canonical_payload(
    schema: str,
    assets: list[object],
) -> bytes:
    return json.dumps(
        {
            "assets": assets,
            "schema": schema,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _validate_expected_paths(
    expected_paths: Sequence[str | os.PathLike[str]] | None,
) -> frozenset[Path] | None:
    if expected_paths is None:
        return None

    canonical = tuple(_canonical_path(item) for item in expected_paths)
    if len(canonical) != len(set(canonical)):
        raise _failure()
    return frozenset(canonical)


def _verify(
    manifest_path: Path,
    public_key: bytes,
    expected_paths: Sequence[str | os.PathLike[str]] | None,
) -> VerifiedModelAssets:
    document = _read_manifest(manifest_path)

    if set(document) != {"schema", "assets", "signature"}:
        raise _failure()

    schema = document["schema"]
    assets = document["assets"]
    signature_text = document["signature"]

    if schema != MANIFEST_SCHEMA:
        raise _failure()
    if not isinstance(assets, list) or not 1 <= len(assets) <= _MAX_ASSETS:
        raise _failure()
    if not isinstance(signature_text, str):
        raise _failure()

    signature = _decode_base64(signature_text, 64)
    payload = _canonical_payload(schema, assets)

    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            payload,
        )
    except (InvalidSignature, ValueError):
        raise _failure() from None

    paths = []
    for entry in assets:
        if not isinstance(entry, dict):
            raise _failure()
        if set(entry) != {"path", "sha256", "size"}:
            raise _failure()

        raw_path = entry["path"]
        expected_digest = entry["sha256"]
        expected_size = entry["size"]

        if not isinstance(raw_path, str):
            raise _failure()
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or expected_digest != expected_digest.lower()
            or any(character not in "0123456789abcdef"
                   for character in expected_digest)
        ):
            raise _failure()
        if (
            type(expected_size) is not int
            or expected_size < 0
        ):
            raise _failure()

        path = _canonical_path(raw_path)
        if path in paths:
            raise _failure()

        actual_digest = _hash_asset(path, expected_size)
        if not hmac.compare_digest(actual_digest, expected_digest):
            raise _failure()

        paths.append(path)

    expected = _validate_expected_paths(expected_paths)
    if expected is not None and frozenset(paths) != expected:
        raise _failure()

    return VerifiedModelAssets(
        manifest_path=manifest_path,
        paths=tuple(paths),
        _public_key=public_key,
    )


def verify_model_asset_manifest(
    manifest_path: str | os.PathLike[str],
    public_key_base64: str,
    *,
    expected_paths: Sequence[str | os.PathLike[str]] | None = None,
) -> VerifiedModelAssets:
    """Authenticate a signed manifest and every exact regular-file asset."""

    try:
        canonical_manifest = _canonical_path(manifest_path)
        public_key = _decode_base64(public_key_base64, 32)
        return _verify(
            canonical_manifest,
            public_key,
            expected_paths,
        )
    except ModelAssetProvenanceError:
        raise
    except Exception:
        raise _failure() from None


def load_verified_model_assets(
    environ: Mapping[str, str] | None = None,
    *,
    expected_paths: Sequence[str | os.PathLike[str]] | None = None,
) -> VerifiedModelAssets:
    """Load trusted-parent configuration and verify its signed assets."""

    source = os.environ if environ is None else environ
    manifest = source.get(MANIFEST_ENV, "").strip()
    public_key = source.get(PUBLIC_KEY_ENV, "").strip()

    if not manifest or not public_key:
        raise _failure()

    return verify_model_asset_manifest(
        manifest,
        public_key,
        expected_paths=expected_paths,
    )


def reverify_model_assets(
    verified: VerifiedModelAssets,
) -> VerifiedModelAssets:
    """Re-authenticate assets after execution before accepting its result."""

    try:
        return _verify(
            verified.manifest_path,
            verified._public_key,
            verified.paths,
        )
    except ModelAssetProvenanceError:
        raise
    except Exception:
        raise _failure() from None
