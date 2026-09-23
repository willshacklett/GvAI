"""Encrypted project workspace for GVAI Private Build Mode.

Trust boundary: the trusted ``WorkspaceBroker`` process owns the adapter,
control plane, identity, and authority. It execs an untrusted worker with only
JSON-lines stdin/stdout pipes. The adapter never generates, returns, logs, or
persists encryption keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, FrozenSet, Protocol, Sequence
import base64
import binascii
import errno
import hashlib
import json
import os
import selectors
import signal
import stat
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class WorkspaceAccessDenied(PermissionError):
    pass


class WorkspaceIntegrityError(RuntimeError):
    pass


class WorkspaceWorkerError(RuntimeError):
    pass


class WorkspaceAuditError(WorkspaceIntegrityError):
    pass


@dataclass(frozen=True)
class WorkspaceRequest:
    worker_id: str
    project_id: str
    operation: str
    path: str


class WorkspaceControlPlane(Protocol):
    """Trusted interface implemented outside the sandboxed worker."""

    def authorize(self, request: WorkspaceRequest) -> bool:
        ...

    def seal(self, plaintext: bytes, associated_data: bytes) -> bytes:
        ...

    def open(self, ciphertext: bytes, associated_data: bytes) -> bytes:
        ...


class AESGCMControlPlane:
    """In-process reference control plane; never pass this object to workers."""

    def __init__(
        self,
        key: bytes,
        authorizer: Callable[[WorkspaceRequest], bool],
    ):
        self.__aead = AESGCM(key)
        self.__authorizer = authorizer

    def authorize(self, request: WorkspaceRequest) -> bool:
        return self.__authorizer(request) is True

    def seal(self, plaintext: bytes, associated_data: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + self.__aead.encrypt(
            nonce,
            plaintext,
            associated_data,
        )

    def open(self, ciphertext: bytes, associated_data: bytes) -> bytes:
        if len(ciphertext) < 13:
            raise WorkspaceIntegrityError("invalid encrypted workspace data")
        try:
            return self.__aead.decrypt(
                ciphertext[:12],
                ciphertext[12:],
                associated_data,
            )
        except (InvalidTag, ValueError) as exc:
            raise WorkspaceIntegrityError(
                "encrypted workspace authentication failed"
            ) from exc


@dataclass(frozen=True)
class WorkspaceAuthority:
    """An immutable server-side operation grant, never sent to the worker."""

    operations: FrozenSet[str]

    def restrict(self, operations: set[str]) -> "WorkspaceAuthority":
        return WorkspaceAuthority(self.operations.intersection(operations))


class WorkspaceAuditSink(Protocol):
    """Externally controlled destination for sanitized audit metadata."""

    def ensure_available(self) -> None:
        ...

    def write(
        self,
        request: WorkspaceRequest,
        allowed: bool,
        reason: str,
    ) -> None:
        ...


class WorkspaceAuditLog:
    """Durable descriptor-anchored reference audit sink.

    This local-file implementation is suitable for development and testing.
    Production deployments should provide a WorkspaceAuditSink backed by
    independently protected storage.
    """

    def __init__(self, path: str | Path):
        configured = Path(path)
        if not configured.is_absolute():
            raise WorkspaceAuditError(
                "workspace audit destination is invalid"
            )

        try:
            configured.parent.mkdir(
                mode=0o700,
                parents=True,
                exist_ok=True,
            )
            directory = configured.parent.resolve(strict=True)
            directory_status = directory.stat()
        except OSError as exc:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from exc

        if configured.parent != directory:
            raise WorkspaceAuditError(
                "workspace audit destination is invalid"
            )
        if (
            not configured.name
            or configured.name in {".", ".."}
            or not stat.S_ISDIR(directory_status.st_mode)
            or directory_status.st_uid != os.geteuid()
            or directory_status.st_mode
            & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise WorkspaceAuditError(
                "workspace audit destination is invalid"
            )

        self.path = directory / configured.name
        self.__directory = directory
        self.__name = configured.name
        self.__directory_identity = (
            directory_status.st_dev,
            directory_status.st_ino,
        )
        self.ensure_available()

    def ensure_available(self) -> None:
        directory = self.__open_directory()
        descriptor = -1
        try:
            descriptor = self.__open_file(directory)
            os.fsync(descriptor)
            os.fsync(directory)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory)

    def write(
        self,
        request: WorkspaceRequest,
        allowed: bool,
        reason: str,
    ) -> None:
        record = {
            "timestamp": time.time(),
            "worker_ref": self._reference("worker", request.worker_id),
            "project_ref": self._reference("project", request.project_id),
            "operation": request.operation,
            "allowed": allowed,
            "reason": reason,
        }
        payload = (
            json.dumps(record, sort_keys=True) + "\n"
        ).encode("utf-8")

        directory = self.__open_directory()
        descriptor = -1
        try:
            descriptor = self.__open_file(directory)
            written = os.write(descriptor, payload)
            if written != len(payload):
                raise WorkspaceAuditError(
                    "workspace audit append was incomplete"
                )
            os.fsync(descriptor)
            os.fsync(directory)
        except WorkspaceAuditError:
            raise
        except OSError as exc:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory)

    def __open_directory(self) -> int:
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        try:
            descriptor = os.open(self.__directory, flags)
        except OSError as exc:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from exc

        try:
            status = os.fstat(descriptor)
            identity = (status.st_dev, status.st_ino)
            if (
                identity != self.__directory_identity
                or not stat.S_ISDIR(status.st_mode)
                or status.st_uid != os.geteuid()
                or status.st_mode
                & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise WorkspaceAuditError(
                    "workspace audit destination is invalid"
                )
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def __open_file(self, directory: int) -> int:
        flags = (
            os.O_WRONLY
            | os.O_APPEND
            | os.O_CREAT
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
            | os.O_NONBLOCK
        )
        try:
            descriptor = os.open(
                self.__name,
                flags,
                0o600,
                dir_fd=directory,
            )
        except OSError as exc:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from exc

        try:
            status = os.fstat(descriptor)
            if (
                not stat.S_ISREG(status.st_mode)
                or status.st_uid != os.geteuid()
                or status.st_nlink != 1
                or status.st_mode
                & (stat.S_IRWXG | stat.S_IRWXO)
            ):
                raise WorkspaceAuditError(
                    "workspace audit destination is invalid"
                )
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    @staticmethod
    def _reference(kind: str, value: str) -> str:
        return hashlib.sha256(
            f"gvai-workspace:{kind}:{value}".encode("utf-8")
        ).hexdigest()


class EncryptedProjectWorkspace:
    """Trusted adapter used only inside the broker process."""

    _FORMAT = b"GVAIWS1\x00"

    def __init__(
        self,
        root: str | Path,
        control_plane: WorkspaceControlPlane,
        audit_log: WorkspaceAuditSink,
    ):
        self.__audit_log = audit_log
        self.__ensure_audit_available()

        self.__root = Path(root).resolve()
        self.__root.mkdir(parents=True, exist_ok=True)
        root_status = self.__root.stat()
        if not stat.S_ISDIR(root_status.st_mode):
            raise ValueError("workspace root must be a directory")
        self.__root_identity = (
            root_status.st_dev,
            root_status.st_ino,
        )
        self.__control_plane = control_plane

    def __ensure_audit_available(self) -> None:
        try:
            self.__audit_log.ensure_available()
        except Exception:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from None

    def __audit(
        self,
        request: WorkspaceRequest,
        allowed: bool,
        reason: str,
    ) -> None:
        try:
            self.__audit_log.write(request, allowed, reason)
        except Exception:
            raise WorkspaceAuditError(
                "workspace audit destination is unavailable"
            ) from None

    def execute(
        self,
        request: WorkspaceRequest,
        authority: WorkspaceAuthority,
        content: bytes | None = None,
    ) -> bytes | None:
        self.__ensure_audit_available()
        try:
            path_parts, normalized = self.__validate_path(
                request.project_id,
                request.path,
            )
        except Exception:
            self.__audit(request, False, "invalid_path")
            raise WorkspaceAccessDenied("workspace request denied") from None

        if request.operation not in authority.operations:
            self.__audit(request, False, "worker_scope_denied")
            raise WorkspaceAccessDenied("workspace operation denied")

        try:
            authorized = self.__control_plane.authorize(request) is True
        except Exception:
            self.__audit(request, False, "control_plane_error")
            raise WorkspaceAccessDenied("workspace request denied") from None

        if not authorized:
            self.__audit(request, False, "control_plane_denied")
            raise WorkspaceAccessDenied("workspace operation denied")

        associated_data = self.__associated_data(
            request.project_id,
            normalized,
        )
        if request.operation == "write":
            try:
                sealed = self.__control_plane.seal(
                    content or b"",
                    associated_data,
                )
                if not isinstance(sealed, bytes):
                    raise TypeError("invalid sealed data")
            except Exception:
                self.__audit(request, False, "seal_failure")
                raise WorkspaceIntegrityError(
                    "workspace operation failed"
                ) from None
            try:
                self.__atomic_write(
                    path_parts,
                    self._FORMAT + sealed,
                )
            except WorkspaceAccessDenied:
                self.__audit(request, False, "invalid_path")
                raise WorkspaceAccessDenied(
                    "workspace request denied"
                ) from None
            except Exception:
                self.__audit(request, False, "storage_failure")
                raise WorkspaceIntegrityError(
                    "workspace operation failed"
                ) from None
            result = None
        elif request.operation == "read":
            try:
                encrypted = self.__read_file(path_parts)
            except WorkspaceAccessDenied:
                self.__audit(request, False, "invalid_path")
                raise WorkspaceAccessDenied(
                    "workspace request denied"
                ) from None
            except OSError:
                self.__audit(request, False, "data_unavailable")
                raise WorkspaceIntegrityError(
                    "encrypted workspace data unavailable"
                ) from None
            if not encrypted.startswith(self._FORMAT):
                self.__audit(request, False, "integrity_failure")
                raise WorkspaceIntegrityError("invalid encrypted workspace data")
            try:
                result = self.__control_plane.open(
                    encrypted[len(self._FORMAT):],
                    associated_data,
                )
                if not isinstance(result, bytes):
                    raise TypeError("invalid opened data")
            except WorkspaceIntegrityError:
                self.__audit(request, False, "integrity_failure")
                raise WorkspaceIntegrityError(
                    "encrypted workspace authentication failed"
                ) from None
            except Exception:
                self.__audit(request, False, "open_failure")
                raise WorkspaceIntegrityError(
                    "workspace operation failed"
                ) from None
        else:
            self.__audit(request, False, "invalid_operation")
            raise WorkspaceAccessDenied("workspace operation denied")

        self.__audit(request, True, "authorized")
        return result

    def audit_invalid_request(self, *, worker_id: str, project_id: str) -> None:
        self.__audit(
            WorkspaceRequest(worker_id, project_id, "invalid", ""),
            False,
            "invalid_request",
        )

    def __validate_path(
        self,
        project_id: str,
        relative_path: str,
    ) -> tuple[tuple[str, ...], str]:
        project = PurePosixPath(str(project_id))
        requested = PurePosixPath(str(relative_path))
        parts = (*project.parts, *requested.parts)

        if (
            project.is_absolute()
            or requested.is_absolute()
            or not project.parts
            or not requested.parts
            or any(part in {"", ".", ".."} for part in parts)
            or any("\x00" in part for part in parts)
        ):
            raise WorkspaceAccessDenied("invalid workspace path")

        return parts, requested.as_posix()

    @staticmethod
    def __associated_data(project_id: str, path: str) -> bytes:
        return json.dumps(
            {"project_id": project_id, "path": path},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def __open_root(self) -> int:
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        try:
            descriptor = os.open(self.__root, flags)
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise WorkspaceAccessDenied(
                    "invalid workspace path"
                ) from exc
            raise

        try:
            root_status = os.fstat(descriptor)
            identity = (root_status.st_dev, root_status.st_ino)
            if identity != self.__root_identity:
                raise WorkspaceAccessDenied(
                    "invalid workspace path"
                )
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def __open_parent(
        self,
        parts: tuple[str, ...],
        *,
        create: bool,
    ) -> tuple[int, str]:
        current = self.__open_root()
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        try:
            for part in parts[:-1]:
                try:
                    following = os.open(part, flags, dir_fd=current)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, 0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                    following = os.open(part, flags, dir_fd=current)

                os.close(current)
                current = following

            return current, parts[-1]
        except Exception as exc:
            os.close(current)
            if (
                isinstance(exc, OSError)
                and exc.errno in {errno.ELOOP, errno.ENOTDIR}
            ):
                raise WorkspaceAccessDenied(
                    "invalid workspace path"
                ) from exc
            raise

    def __read_file(
        self,
        parts: tuple[str, ...],
    ) -> bytes:
        parent, name = self.__open_parent(parts, create=False)
        descriptor = -1
        try:
            try:
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_CLOEXEC
                    | os.O_NONBLOCK,
                    dir_fd=parent,
                )
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise WorkspaceAccessDenied(
                        "invalid workspace path"
                    ) from exc
                raise

            file_status = os.fstat(descriptor)
            if not stat.S_ISREG(file_status.st_mode):
                raise WorkspaceAccessDenied(
                    "invalid workspace path"
                )

            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def __atomic_write(
        self,
        parts: tuple[str, ...],
        content: bytes,
    ) -> None:
        parent, name = self.__open_parent(parts, create=True)
        descriptor = -1
        temp_name: str | None = None

        try:
            try:
                target_status = os.stat(
                    name,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                target_status = None

            if (
                target_status is not None
                and not stat.S_ISREG(target_status.st_mode)
            ):
                raise WorkspaceAccessDenied(
                    "invalid workspace path"
                )

            temp_name = (
                f".{name}.{os.urandom(16).hex()}.tmp"
            )
            descriptor = os.open(
                temp_name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=parent,
            )

            pending = memoryview(content)
            while pending:
                written = os.write(descriptor, pending)
                if written <= 0:
                    raise OSError("workspace write failed")
                pending = pending[written:]

            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1

            os.replace(
                temp_name,
                name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
            )
            temp_name = None
            os.fsync(parent)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temp_name is not None:
                try:
                    os.unlink(temp_name, dir_fd=parent)
                except FileNotFoundError:
                    pass
            os.close(parent)


class WorkspaceBroker:
    """Trusted parent that binds server-side session state to worker requests."""

    _MAX_REQUEST_BYTES = 16 * 1024 * 1024
    _MAX_RESPONSE_BYTES = 16 * 1024 * 1024
    _ENV_ALLOWLIST = frozenset({"LANG", "LC_ALL", "PATH", "TZ"})

    def __init__(
        self,
        workspace: EncryptedProjectWorkspace,
        *,
        worker_id: str,
        project_id: str,
        authority: WorkspaceAuthority,
    ):
        self.__workspace = workspace
        self.__worker_id = str(worker_id)
        self.__project_id = str(project_id)
        self.__authority = authority

    def run_worker(
        self,
        command: Sequence[str],
        *,
        timeout: float = 30.0,
        extra_env: dict[str, str] | None = None,
    ) -> int:
        resolved_command = [str(part) for part in command]
        if not resolved_command:
            raise WorkspaceWorkerError("workspace worker failed")

        # extra_env may only add names the broker does not itself manage.
        # A caller (bug or otherwise) attempting to override a broker-owned
        # variable (e.g. PATH) through this channel fails closed instead of
        # silently winning the collision.
        if extra_env and any(
            str(name) in self._ENV_ALLOWLIST for name in extra_env
        ):
            raise WorkspaceWorkerError("workspace worker failed")

        environment = {
            name: value
            for name, value in os.environ.items()
            if name in self._ENV_ALLOWLIST
        }
        # Callers may add a narrow set of non-secret config values (e.g. an
        # inference command name). This never widens beyond what the caller
        # explicitly hands in; the full parent environment is still filtered
        # through the allowlist above.
        if extra_env:
            for name, value in extra_env.items():
                environment[str(name)] = str(value)
        environment.setdefault("PATH", os.defpath)
        environment["PYTHONUNBUFFERED"] = "1"

        response_read, response_write = os.pipe()
        request_read, request_write = os.pipe()
        file_actions = [
            (os.POSIX_SPAWN_DUP2, response_read, 0),
            (os.POSIX_SPAWN_DUP2, request_write, 1),
            (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0o600),
            (os.POSIX_SPAWN_CLOSEFROM, 3),
        ]
        try:
            process_id = os.posix_spawnp(
                resolved_command[0],
                resolved_command,
                environment,
                file_actions=file_actions,
                setsid=True,
            )
        except Exception:
            for descriptor in (
                response_read,
                response_write,
                request_read,
                request_write,
            ):
                os.close(descriptor)
            raise WorkspaceWorkerError("workspace worker failed") from None

        response_stream = None
        request_stream = None
        process_descriptor = None
        try:
            os.close(response_read)
            response_read = -1
            os.close(request_write)
            request_write = -1
            response_stream = os.fdopen(response_write, "wb", buffering=0)
            response_write = -1
            os.set_blocking(response_stream.fileno(), False)
            request_stream = os.fdopen(request_read, "rb", buffering=0)
            request_read = -1
            process_descriptor = os.pidfd_open(process_id)
        except Exception:
            for descriptor in (
                response_read,
                response_write,
                request_read,
                request_write,
            ):
                if descriptor >= 0:
                    os.close(descriptor)
            if response_stream is not None:
                response_stream.close()
            if request_stream is not None:
                request_stream.close()
            self.__terminate_worker_group(process_id)
            self.__reap(process_id)
            raise WorkspaceWorkerError("workspace worker failed") from None

        selector = selectors.DefaultSelector()
        selector.register(request_stream, selectors.EVENT_READ)
        pending = b""
        request_count = 0
        deadline = time.monotonic() + timeout
        process_reaped = False

        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkspaceWorkerError("workspace worker failed")
                events = selector.select(remaining)
                if not events:
                    raise WorkspaceWorkerError("workspace worker failed")
                chunk = os.read(request_stream.fileno(), 65536)
                if not chunk:
                    break
                pending += chunk
                if len(pending) > self._MAX_REQUEST_BYTES:
                    raise WorkspaceWorkerError("workspace worker failed")
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    response = self.__handle_request(line)
                    self.__write_response(
                        response_stream.fileno(),
                        response,
                        deadline,
                    )
                    request_count += 1

            if pending.strip():
                self.__workspace.audit_invalid_request(
                    worker_id=self.__worker_id,
                    project_id=self.__project_id,
                )
                raise WorkspaceWorkerError("workspace worker failed")

            response_stream.close()
            selector.unregister(request_stream)
            selector.register(process_descriptor, selectors.EVENT_READ)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise WorkspaceWorkerError("workspace worker failed")
            # Inspect without reaping: failure cleanup must signal the
            # group before releasing the leader's PID for reuse.
            exit_info = os.waitid(
                os.P_PID,
                process_id,
                os.WEXITED | os.WNOWAIT,
            )
            if (
                exit_info.si_code != os.CLD_EXITED
                or exit_info.si_status != 0
            ):
                raise WorkspaceWorkerError("workspace worker failed")
            os.waitpid(process_id, 0)
            process_reaped = True
        except Exception:
            if not process_reaped:
                self.__terminate_worker_group(process_id)
                self.__reap(process_id)
                process_reaped = True
            raise WorkspaceWorkerError("workspace worker failed") from None
        finally:
            selector.close()
            os.close(process_descriptor)
            request_stream.close()
            if not response_stream.closed:
                response_stream.close()

        return request_count

    @staticmethod
    def __terminate_worker_group(process_id: int) -> None:
        """Kill the worker's original process group, not just its leader.

        ``run_worker`` always spawns with ``setsid=True``, so the worker
        becomes the leader of a brand-new session and process group whose
        id equals its own pid -- distinct from the broker's own process
        group. Signaling that group (rather than only the leader pid)
        reaches descendants that remain in that process group.
        Descendants that create or join another process group are not
        contained by this mechanism. This is not complete process-tree
        containment.

        This fails directly to SIGKILL (no graceful phase) to match the
        existing fail-secure timeout/error handling in this method.
        """

        try:
            os.killpg(process_id, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

        # Defensive fallback in case the leader was somehow not its own
        # process group (should not happen with setsid=True).
        try:
            os.kill(process_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    @staticmethod
    def __reap(process_id: int) -> None:
        try:
            os.waitpid(process_id, 0)
        except ChildProcessError:
            pass

    def __write_response(
        self,
        descriptor: int,
        response: dict[str, object],
        deadline: float,
    ) -> None:
        frame = json.dumps(response, sort_keys=True).encode("utf-8") + b"\n"
        if len(frame) > self._MAX_RESPONSE_BYTES:
            raise WorkspaceWorkerError("workspace worker failed")

        pending = memoryview(frame)
        with selectors.DefaultSelector() as write_selector:
            write_selector.register(descriptor, selectors.EVENT_WRITE)
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not write_selector.select(remaining):
                    raise WorkspaceWorkerError("workspace worker failed")
                try:
                    written = os.write(descriptor, pending)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError:
                    raise WorkspaceWorkerError("workspace worker failed") from None
                if written <= 0:
                    raise WorkspaceWorkerError("workspace worker failed")
                pending = pending[written:]

    def __handle_request(self, raw: bytes) -> dict[str, object]:
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid request")
            operation = payload.get("operation")
            path = payload.get("path")
            if not isinstance(path, str):
                raise ValueError("invalid request")

            if operation == "read" and set(payload) == {"operation", "path"}:
                content = None
            elif operation == "write" and set(payload) == {
                "operation",
                "path",
                "content_b64",
            }:
                encoded = payload["content_b64"]
                if not isinstance(encoded, str):
                    raise ValueError("invalid request")
                content = base64.b64decode(encoded, validate=True)
            else:
                raise ValueError("invalid request")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, binascii.Error):
            self.__workspace.audit_invalid_request(
                worker_id=self.__worker_id,
                project_id=self.__project_id,
            )
            return {"ok": False, "error": "workspace request denied"}

        request = WorkspaceRequest(
            self.__worker_id,
            self.__project_id,
            operation,
            path,
        )
        try:
            result = self.__workspace.execute(
                request,
                self.__authority,
                content,
            )
        except WorkspaceAccessDenied:
            return {"ok": False, "error": "workspace request denied"}
        except WorkspaceIntegrityError:
            return {"ok": False, "error": "workspace operation failed"}
        except Exception:
            return {"ok": False, "error": "workspace operation failed"}

        response: dict[str, object] = {"ok": True}
        if result is not None:
            response["content_b64"] = base64.b64encode(result).decode("ascii")
        return response
