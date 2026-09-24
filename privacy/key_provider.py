"""Externally controlled key provider for the private workspace."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import socket
import stat
import struct
import sys
from typing import FrozenSet


WORKSPACE_KEY_SOCKET_ENV = "GVAI_PRIVATE_WORKSPACE_KEY_SOCKET"
WORKSPACE_KEY_PROVIDER_UID_ENV = "GVAI_PRIVATE_WORKSPACE_KEY_PROVIDER_UID"

KEY_PROVIDER_ENV_NAMES = frozenset(
    {
        WORKSPACE_KEY_SOCKET_ENV,
        WORKSPACE_KEY_PROVIDER_UID_ENV,
    }
)

_REQUEST = b"GVAI-PRIVATE-WORKSPACE-KEY-V1\n"
_KEY_BYTES = 32
_MAX_RESPONSE_BYTES = _KEY_BYTES + 1
_DEFAULT_TIMEOUT = 2.0
_GENERIC_ERROR = "GVAI private workspace key provider failed."


class WorkspaceKeyProviderError(RuntimeError):
    """The trusted parent could not obtain a valid workspace key."""


@dataclass(frozen=True)
class WorkspaceKeyProviderConfiguration:
    socket_path: Path
    allowed_peer_uids: FrozenSet[int]
    timeout: float = _DEFAULT_TIMEOUT


def load_workspace_key_from_provider(
    *,
    environ: dict[str, str] | os._Environ[str] | None = None,
) -> bytes:
    """Retrieve exactly 32 raw key bytes from a trusted local provider.

    The provider endpoint and expected peer identity are operator-owned
    configuration. The request contains no worker input, project identity,
    authority, path, prompt, or key material.
    """

    environment = os.environ if environ is None else environ

    try:
        configuration, identity = _load_configuration(environment)

        with socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        ) as client:
            client.settimeout(configuration.timeout)
            client.connect(str(configuration.socket_path))

            current_identity = _socket_identity(
                configuration.socket_path,
                configuration.allowed_peer_uids,
            )
            if current_identity != identity:
                raise _error()

            peer_uid = _peer_uid(client)
            if peer_uid not in configuration.allowed_peer_uids:
                raise _error()

            client.sendall(_REQUEST)
            client.shutdown(socket.SHUT_WR)

            response = bytearray()
            while True:
                chunk = client.recv(_MAX_RESPONSE_BYTES)
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > _KEY_BYTES:
                    raise _error()

        if len(response) != _KEY_BYTES:
            raise _error()

        return bytes(response)
    except WorkspaceKeyProviderError:
        raise
    except Exception:
        raise _error() from None


def _load_configuration(
    environment: dict[str, str] | os._Environ[str],
) -> tuple[
    WorkspaceKeyProviderConfiguration,
    tuple[int, int, int, int, int],
]:
    raw_path = environment.get(WORKSPACE_KEY_SOCKET_ENV, "")
    if not raw_path or raw_path != raw_path.strip():
        raise _error()

    path = Path(raw_path)
    if not path.is_absolute():
        raise _error()

    raw_uid = environment.get(
        WORKSPACE_KEY_PROVIDER_UID_ENV,
        "",
    )
    if raw_uid:
        if raw_uid != raw_uid.strip() or not raw_uid.isdecimal():
            raise _error()
        provider_uid = int(raw_uid, 10)
        if provider_uid < 0 or str(provider_uid) != raw_uid:
            raise _error()
        allowed_peer_uids = frozenset({provider_uid})
    else:
        allowed_peer_uids = frozenset({0, os.geteuid()})

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _error() from None

    if resolved != path:
        raise _error()

    configuration = WorkspaceKeyProviderConfiguration(
        socket_path=path,
        allowed_peer_uids=allowed_peer_uids,
    )
    identity = _socket_identity(path, allowed_peer_uids)
    return configuration, identity


def _socket_identity(
    path: Path,
    allowed_peer_uids: FrozenSet[int],
) -> tuple[int, int, int, int, int]:
    try:
        status = os.stat(path, follow_symlinks=False)
    except OSError:
        raise _error() from None

    mode = stat.S_IMODE(status.st_mode)
    if (
        not stat.S_ISSOCK(status.st_mode)
        or status.st_uid not in allowed_peer_uids
        or mode & 0o022
        or status.st_nlink != 1
    ):
        raise _error()

    return (
        status.st_dev,
        status.st_ino,
        status.st_uid,
        status.st_gid,
        mode,
    )


def _peer_uid(client: socket.socket) -> int:
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise _error()

    size = struct.calcsize("3i")
    try:
        credentials = client.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            size,
        )
        process_id, peer_uid, peer_gid = struct.unpack(
            "3i",
            credentials,
        )
    except (OSError, struct.error):
        raise _error() from None

    if process_id <= 0 or peer_uid < 0 or peer_gid < 0:
        raise _error()

    return peer_uid


def _error() -> WorkspaceKeyProviderError:
    return WorkspaceKeyProviderError(_GENERIC_ERROR)
