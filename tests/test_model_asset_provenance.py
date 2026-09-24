import base64
import hashlib
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from privacy.model_asset_provenance import (
    MANIFEST_ENV,
    MANIFEST_SCHEMA,
    PUBLIC_KEY_ENV,
    ModelAssetProvenanceError,
    load_verified_model_assets,
    reverify_model_assets,
    verify_model_asset_manifest,
)


def _entry(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": str(path.resolve(strict=True)),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _public_key_text(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def _write_signed_manifest(
    tmp_path: Path,
    entries: list[dict[str, object]],
    *,
    private_key: Ed25519PrivateKey | None = None,
    name: str = "manifest.json",
) -> tuple[Path, str, Ed25519PrivateKey]:
    key = private_key or Ed25519PrivateKey.generate()
    payload = json.dumps(
        {
            "assets": entries,
            "schema": MANIFEST_SCHEMA,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = base64.b64encode(key.sign(payload)).decode("ascii")
    manifest = tmp_path / name
    manifest.write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "assets": entries,
                "signature": signature,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest.resolve(strict=True), _public_key_text(key), key


def test_valid_signed_manifest_returns_exact_assets(tmp_path):
    model = tmp_path / "model.gguf"
    tokenizer = tmp_path / "tokenizer.json"
    model.write_bytes(b"synthetic-model-weights")
    tokenizer.write_bytes(b'{"tokenizer":"synthetic"}')

    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(model), _entry(tokenizer)],
    )

    verified = verify_model_asset_manifest(
        manifest,
        public_key,
        expected_paths=(model, tokenizer),
    )

    assert verified.manifest_path == manifest
    assert verified.paths == (
        model.resolve(strict=True),
        tokenizer.resolve(strict=True),
    )
    assert reverify_model_assets(verified).paths == verified.paths


def test_environment_loader_requires_external_trust_configuration(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"model")
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )

    verified = load_verified_model_assets(
        {
            MANIFEST_ENV: str(manifest),
            PUBLIC_KEY_ENV: public_key,
        },
        expected_paths=(asset,),
    )
    assert verified.paths == (asset.resolve(strict=True),)

    for missing in (MANIFEST_ENV, PUBLIC_KEY_ENV):
        environment = {
            MANIFEST_ENV: str(manifest),
            PUBLIC_KEY_ENV: public_key,
        }
        del environment[missing]
        with pytest.raises(ModelAssetProvenanceError):
            load_verified_model_assets(environment)


def test_wrong_signature_is_rejected_without_sensitive_output(tmp_path):
    asset = tmp_path / "highly-secret-model-name.gguf"
    asset.write_bytes(b"SECRET-MODEL-CANARY")
    manifest, _, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )
    wrong_key = _public_key_text(Ed25519PrivateKey.generate())

    with pytest.raises(ModelAssetProvenanceError) as excinfo:
        verify_model_asset_manifest(manifest, wrong_key)

    message = str(excinfo.value)
    assert "SECRET-MODEL-CANARY" not in message
    assert str(asset) not in message


def test_changed_asset_content_is_rejected(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"approved-content")
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )

    asset.write_bytes(b"tampered-content")

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


def test_post_execution_reverification_detects_mutation(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"approved-content")
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )
    verified = verify_model_asset_manifest(manifest, public_key)

    asset.write_bytes(b"changed-after-initial-verification")

    with pytest.raises(ModelAssetProvenanceError):
        reverify_model_assets(verified)


def test_manifest_assets_must_exactly_match_mount_policy(tmp_path):
    first = tmp_path / "first.gguf"
    second = tmp_path / "second.json"
    undeclared = tmp_path / "undeclared.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    undeclared.write_bytes(b"undeclared")

    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(first), _entry(second)],
    )

    verify_model_asset_manifest(
        manifest,
        public_key,
        expected_paths=(second, first),
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(
            manifest,
            public_key,
            expected_paths=(first, undeclared),
        )


def test_duplicate_asset_entry_is_rejected(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"model")
    entry = _entry(asset)
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [entry, dict(entry)],
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


def test_asset_symlink_is_rejected(tmp_path):
    target = tmp_path / "model.gguf"
    alias = tmp_path / "model-link.gguf"
    target.write_bytes(b"model")
    alias.symlink_to(target)
    entry = _entry(target)
    entry["path"] = str(alias.absolute())
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [entry],
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


def test_manifest_symlink_is_rejected(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"model")
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )
    alias = tmp_path / "manifest-link.json"
    alias.symlink_to(manifest)

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(alias.absolute(), public_key)


def test_directory_asset_is_rejected(tmp_path):
    directory = tmp_path / "model-directory"
    directory.mkdir()
    entry = {
        "path": str(directory.resolve(strict=True)),
        "sha256": hashlib.sha256(b"").hexdigest(),
        "size": 0,
    }
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [entry],
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


def test_hard_linked_asset_is_rejected(tmp_path):
    asset = tmp_path / "model.gguf"
    alias = tmp_path / "model-alias.gguf"
    asset.write_bytes(b"model")
    os.link(asset, alias)
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [_entry(asset)],
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda entry: entry.update({"size": True}),
        lambda entry: entry.update({"size": -1}),
        lambda entry: entry.update({"sha256": "A" * 64}),
        lambda entry: entry.update({"sha256": "not-a-digest"}),
        lambda entry: entry.update({"extra": "unapproved"}),
    ],
)
def test_malformed_signed_asset_entries_are_rejected(tmp_path, mutator):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"model")
    entry = _entry(asset)
    mutator(entry)
    manifest, public_key, _ = _write_signed_manifest(
        tmp_path,
        [entry],
    )

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(manifest, public_key)


def test_duplicate_json_keys_are_rejected_before_trust(tmp_path):
    asset = tmp_path / "model.gguf"
    asset.write_bytes(b"model")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"schema":"gvai-private-model-assets-v1",'
        '"schema":"gvai-private-model-assets-v1",'
        '"assets":[],"signature":""}',
        encoding="utf-8",
    )
    public_key = _public_key_text(Ed25519PrivateKey.generate())

    with pytest.raises(ModelAssetProvenanceError):
        verify_model_asset_manifest(
            manifest.resolve(strict=True),
            public_key,
        )
