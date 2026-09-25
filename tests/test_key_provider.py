from __future__ import annotations

import base64
import os
from pathlib import Path
import socket
import threading

import pytest

import privacy.key_provider as key_provider
import privacy.runtime as runtime
from privacy.key_provider import (
    KEY_PROVIDER_ENV_NAMES,
    WORKSPACE_KEY_PROVIDER_UID_ENV,
    WORKSPACE_KEY_SOCKET_ENV,
    WorkspaceKeyProviderError,
    load_workspace_key_from_provider,
)


EXPECTED_REQUEST = b"GVAI-PRIVATE-WORKSPACE-KEY-V1\n"
KEY = bytes(range(32))


def _start_provider(path: Path, response: bytes):
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    path.chmod(0o600)
    listener.listen(1)

    state = {
        "request": None,
        "errors": [],
    }

    def serve():
        try:
            connection, _ = listener.accept()
            with connection:
                request = bytearray()
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    request.extend(chunk)
                state["request"] = bytes(request)
                connection.sendall(response)
        except BaseException as exc:
            state["errors"].append(exc)
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread, state


def _finish(thread, state):
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert state["errors"] == []


class _ObservedClient:
    def __init__(self):
        self.events = []
        self.closed = False

    def __enter__(self):
        self.events.append(("enter",))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True
        self.events.append(("exit", exc_type))
        return False

    def settimeout(self, timeout):
        self.events.append(("settimeout", timeout))

    def connect(self, path):
        self.events.append(("connect", path))

    def sendall(self, payload):
        self.events.append(("sendall", payload))

    def shutdown(self, how):
        self.events.append(("shutdown", how))

    def recv(self, size):
        self.events.append(("recv", size))
        return b""


def test_replaced_endpoint_is_rejected_before_request(
    monkeypatch,
    tmp_path,
):
    endpoint = tmp_path / "provider.sock"
    endpoint.write_bytes(b"identity-anchor")
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))

    original_identity = (1, 10, os.geteuid(), os.getegid(), 0o600)
    replacement_identity = (1, 11, os.geteuid(), os.getegid(), 0o600)
    identities = iter((original_identity, replacement_identity))

    monkeypatch.setattr(
        key_provider,
        "_socket_identity",
        lambda path, allowed: next(identities),
    )

    client = _ObservedClient()
    monkeypatch.setattr(
        key_provider.socket,
        "socket",
        lambda *args, **kwargs: client,
    )

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    assert str(excinfo.value) == (
        "GVAI private workspace key provider failed."
    )
    assert any(event[0] == "connect" for event in client.events)
    assert not any(event[0] == "sendall" for event in client.events)
    assert not any(event[0] == "recv" for event in client.events)
    assert client.closed is True


def test_unapproved_peer_uid_is_rejected_before_request(
    monkeypatch,
    tmp_path,
):
    endpoint = tmp_path / "provider.sock"
    endpoint.write_bytes(b"identity-anchor")
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))

    identity = (1, 10, os.geteuid(), os.getegid(), 0o600)
    monkeypatch.setattr(
        key_provider,
        "_socket_identity",
        lambda path, allowed: identity,
    )

    unexpected_uid = os.geteuid() + 1
    if unexpected_uid == 0:
        unexpected_uid += 1
    monkeypatch.setattr(
        key_provider,
        "_peer_uid",
        lambda client: unexpected_uid,
    )

    client = _ObservedClient()
    monkeypatch.setattr(
        key_provider.socket,
        "socket",
        lambda *args, **kwargs: client,
    )

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    assert str(excinfo.value) == (
        "GVAI private workspace key provider failed."
    )
    assert any(event[0] == "connect" for event in client.events)
    assert not any(event[0] == "sendall" for event in client.events)
    assert not any(event[0] == "recv" for event in client.events)
    assert client.closed is True


def test_provider_returns_exact_raw_key(monkeypatch, tmp_path):
    endpoint = tmp_path / "key-provider.sock"
    thread, state = _start_provider(endpoint, KEY)

    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))
    key = load_workspace_key_from_provider()

    _finish(thread, state)
    assert key == KEY
    assert state["request"] == EXPECTED_REQUEST


def test_explicit_current_peer_uid_is_accepted(monkeypatch, tmp_path):
    endpoint = tmp_path / "key-provider.sock"
    thread, state = _start_provider(endpoint, KEY)

    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))
    monkeypatch.setenv(
        WORKSPACE_KEY_PROVIDER_UID_ENV,
        str(os.geteuid()),
    )

    assert load_workspace_key_from_provider() == KEY
    _finish(thread, state)


@pytest.mark.parametrize(
    "response",
    [
        b"",
        b"short",
        KEY + b"x",
    ],
)
def test_invalid_response_length_fails_closed(
    monkeypatch,
    tmp_path,
    response,
):
    endpoint = tmp_path / "key-provider.sock"
    thread, state = _start_provider(endpoint, response)
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))

    with pytest.raises(
        WorkspaceKeyProviderError,
        match="private workspace key provider failed",
    ):
        load_workspace_key_from_provider()

    _finish(thread, state)


def test_missing_endpoint_configuration_is_sanitized(monkeypatch):
    monkeypatch.delenv(WORKSPACE_KEY_SOCKET_ENV, raising=False)

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    assert str(excinfo.value) == (
        "GVAI private workspace key provider failed."
    )


def test_relative_endpoint_is_rejected_without_path_disclosure(
    monkeypatch,
):
    sensitive_path = "sensitive/provider.sock"
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, sensitive_path)

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    assert sensitive_path not in str(excinfo.value)


def test_symlink_endpoint_is_rejected(monkeypatch, tmp_path):
    target = tmp_path / "provider.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(target))
    target.chmod(0o600)

    alias = tmp_path / "provider-alias.sock"
    alias.symlink_to(target)

    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(alias))
    try:
        with pytest.raises(WorkspaceKeyProviderError):
            load_workspace_key_from_provider()
    finally:
        listener.close()


def test_group_or_world_writable_endpoint_is_rejected(
    monkeypatch,
    tmp_path,
):
    endpoint = tmp_path / "provider.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(endpoint))
    endpoint.chmod(0o622)

    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))
    try:
        with pytest.raises(WorkspaceKeyProviderError):
            load_workspace_key_from_provider()
    finally:
        listener.close()


def test_non_socket_endpoint_is_rejected(monkeypatch, tmp_path):
    endpoint = tmp_path / "provider.sock"
    endpoint.write_text("not-a-socket", encoding="utf-8")
    endpoint.chmod(0o600)
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))

    with pytest.raises(WorkspaceKeyProviderError):
        load_workspace_key_from_provider()


@pytest.mark.parametrize(
    "configured_uid",
    [
        "-1",
        "+1",
        "01",
        "not-a-uid",
        " 1000",
    ],
)
def test_invalid_provider_uid_is_sanitized(
    monkeypatch,
    configured_uid,
):
    sensitive_endpoint = "/sensitive/key-provider.sock"
    monkeypatch.setenv(
        WORKSPACE_KEY_SOCKET_ENV,
        sensitive_endpoint,
    )
    monkeypatch.setenv(
        WORKSPACE_KEY_PROVIDER_UID_ENV,
        configured_uid,
    )

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    assert configured_uid not in str(excinfo.value)
    assert sensitive_endpoint not in str(excinfo.value)


def test_malformed_provider_response_is_not_disclosed(
    monkeypatch,
    tmp_path,
):
    endpoint = tmp_path / "provider.sock"
    sensitive_response = b"SENSITIVE-PROVIDER-RESPONSE-" * 2
    thread, state = _start_provider(endpoint, sensitive_response)
    monkeypatch.setenv(WORKSPACE_KEY_SOCKET_ENV, str(endpoint))

    with pytest.raises(WorkspaceKeyProviderError) as excinfo:
        load_workspace_key_from_provider()

    _finish(thread, state)
    assert "SENSITIVE-PROVIDER-RESPONSE" not in str(excinfo.value)



def test_runtime_prefers_external_provider_over_environment_key(
    monkeypatch,
):
    environment_canary = base64.b64encode(
        b"environment-key-must-not-be-used"
    ).decode("ascii")
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        environment_canary,
    )
    monkeypatch.setenv(
        WORKSPACE_KEY_SOCKET_ENV,
        "/synthetic/provider.sock",
    )
    monkeypatch.setattr(
        runtime,
        "load_workspace_key_from_provider",
        lambda: KEY,
    )

    assert runtime.load_trusted_workspace_key() == KEY


def test_runtime_provider_failure_never_uses_environment_fallback(
    monkeypatch,
):
    environment_key = base64.b64encode(KEY).decode("ascii")
    sensitive_socket = "/sensitive/provider.sock"
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        environment_key,
    )
    monkeypatch.setenv(
        WORKSPACE_KEY_SOCKET_ENV,
        sensitive_socket,
    )

    def fail_provider():
        raise WorkspaceKeyProviderError(
            "sensitive provider implementation detail"
        )

    monkeypatch.setattr(
        runtime,
        "load_workspace_key_from_provider",
        fail_provider,
    )

    with pytest.raises(RuntimeError) as excinfo:
        runtime.load_trusted_workspace_key()

    assert str(excinfo.value) == (
        "GVAI encrypted workspace key provider failed."
    )
    assert sensitive_socket not in str(excinfo.value)
    assert environment_key not in str(excinfo.value)
    assert "implementation detail" not in str(excinfo.value)


def test_partial_provider_configuration_disables_environment_fallback(
    monkeypatch,
):
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        base64.b64encode(KEY).decode("ascii"),
    )
    monkeypatch.delenv(
        WORKSPACE_KEY_SOCKET_ENV,
        raising=False,
    )
    monkeypatch.setenv(
        WORKSPACE_KEY_PROVIDER_UID_ENV,
        str(os.geteuid()),
    )

    with pytest.raises(RuntimeError) as excinfo:
        runtime.load_trusted_workspace_key()

    assert str(excinfo.value) == (
        "GVAI encrypted workspace key provider failed."
    )


def test_key_provider_configuration_is_forbidden_from_worker():
    assert KEY_PROVIDER_ENV_NAMES <= (
        runtime._FORBIDDEN_EXTRA_ENV_NAMES
    )
