"""Externally controlled resource policy for private workers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import sys
import time
from typing import Mapping, Sequence
import uuid


class ResourceContainmentError(RuntimeError):
    """Resource containment could not be configured safely."""


CGROUP_ROOT_ENV = "GVAI_PRIVATE_CGROUP_ROOT"
MEMORY_MAX_ENV = "GVAI_PRIVATE_MEMORY_MAX_BYTES"
PIDS_MAX_ENV = "GVAI_PRIVATE_PIDS_MAX"
CPU_QUOTA_ENV = "GVAI_PRIVATE_CPU_QUOTA_US"
CPU_PERIOD_ENV = "GVAI_PRIVATE_CPU_PERIOD_US"

RESOURCE_POLICY_ENV_NAMES = frozenset(
    {
        CGROUP_ROOT_ENV,
        MEMORY_MAX_ENV,
        PIDS_MAX_ENV,
        CPU_QUOTA_ENV,
        CPU_PERIOD_ENV,
    }
)

DEFAULT_MEMORY_MAX_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_PIDS_MAX = 64
DEFAULT_CPU_QUOTA_US = 400_000
DEFAULT_CPU_PERIOD_US = 100_000

_MIN_MEMORY_BYTES = 128 * 1024 * 1024
_MAX_MEMORY_BYTES = 1024 * 1024 * 1024 * 1024
_MIN_PIDS = 8
_MAX_PIDS = 4096
_MIN_CPU_US = 1_000
_MAX_CPU_PERIOD_US = 1_000_000
_MAX_CPU_COUNT = 128


@dataclass(frozen=True)
class WorkerResourceLimits:
    memory_max_bytes: int
    pids_max: int
    cpu_quota_us: int
    cpu_period_us: int

    @property
    def cpu_max(self) -> str:
        return f"{self.cpu_quota_us} {self.cpu_period_us}"


@dataclass(frozen=True)
class WorkerResourceConfiguration:
    cgroup_root: Path
    limits: WorkerResourceLimits


def _invalid() -> ResourceContainmentError:
    return ResourceContainmentError(
        "private worker resource configuration is invalid"
    )


def _bounded_integer(
    environment: Mapping[str, str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = environment.get(name)
    if raw in (None, ""):
        return default

    value_text = str(raw)
    if (
        value_text != value_text.strip()
        or not value_text.isascii()
        or not value_text.isdecimal()
    ):
        raise _invalid()

    try:
        value = int(value_text, 10)
    except (TypeError, ValueError, OverflowError):
        raise _invalid() from None

    if not minimum <= value <= maximum:
        raise _invalid()

    return value


def load_worker_resource_configuration(
    environment: Mapping[str, str] | None = None,
) -> WorkerResourceConfiguration:
    """Load trusted-parent policy without exposing raw values in errors."""

    if sys.platform != "linux":
        raise ResourceContainmentError(
            "private worker resource containment requires Linux"
        )

    source = os.environ if environment is None else environment

    raw_root = str(source.get(CGROUP_ROOT_ENV, "/sys/fs/cgroup"))
    root = Path(raw_root)

    if not root.is_absolute() or root == Path("/"):
        raise _invalid()

    try:
        resolved_root = root.resolve(strict=True)
    except OSError:
        raise _invalid() from None

    if resolved_root != root or not resolved_root.is_dir():
        raise _invalid()

    memory_max = _bounded_integer(
        source,
        MEMORY_MAX_ENV,
        DEFAULT_MEMORY_MAX_BYTES,
        _MIN_MEMORY_BYTES,
        _MAX_MEMORY_BYTES,
    )
    pids_max = _bounded_integer(
        source,
        PIDS_MAX_ENV,
        DEFAULT_PIDS_MAX,
        _MIN_PIDS,
        _MAX_PIDS,
    )
    cpu_period = _bounded_integer(
        source,
        CPU_PERIOD_ENV,
        DEFAULT_CPU_PERIOD_US,
        _MIN_CPU_US,
        _MAX_CPU_PERIOD_US,
    )
    cpu_quota = _bounded_integer(
        source,
        CPU_QUOTA_ENV,
        DEFAULT_CPU_QUOTA_US,
        _MIN_CPU_US,
        _MAX_CPU_PERIOD_US * _MAX_CPU_COUNT,
    )

    if cpu_quota > cpu_period * _MAX_CPU_COUNT:
        raise _invalid()

    return WorkerResourceConfiguration(
        cgroup_root=resolved_root,
        limits=WorkerResourceLimits(
            memory_max_bytes=memory_max,
            pids_max=pids_max,
            cpu_quota_us=cpu_quota,
            cpu_period_us=cpu_period,
        ),
    )


def _trusted_file(
    path: Path,
    *,
    executable: bool,
) -> Path:
    if not path.is_absolute():
        raise ResourceContainmentError(
            "private worker staging command is invalid"
        )

    try:
        resolved = path.resolve(strict=True)
        status = resolved.stat()
    except OSError:
        raise ResourceContainmentError(
            "private worker staging command is invalid"
        ) from None

    mode = stat.S_IMODE(status.st_mode)
    owner_is_root = status.st_uid == 0
    owner_is_operator = status.st_uid == os.geteuid()

    if (
        resolved != path
        or not stat.S_ISREG(status.st_mode)
        or not (owner_is_root or owner_is_operator)
        or mode & 0o002
        or owner_is_root and mode & 0o020
        or executable
        and not os.access(resolved, os.X_OK)
    ):
        raise ResourceContainmentError(
            "private worker staging command is invalid"
        )

    return resolved


def build_staged_worker_command(
    worker_command: Sequence[str],
) -> list[str]:
    """Prefix a trusted worker command with the stop-before-exec launcher."""

    command = [str(part) for part in worker_command]
    if not command:
        raise ResourceContainmentError(
            "private worker staging command is invalid"
        )

    worker_executable = _trusted_file(
        Path(command[0]),
        executable=True,
    )
    python_executable = _trusted_file(
        Path(sys.executable).resolve(strict=True),
        executable=True,
    )
    launcher = _trusted_file(
        Path(__file__).resolve(strict=True).with_name(
            "resource_staging_launcher.py"
        ),
        executable=False,
    )

    command[0] = str(worker_executable)

    return [
        str(python_executable),
        str(launcher),
        *command,
    ]


_REQUIRED_CONTROLLERS = frozenset({"cpu", "memory", "pids"})
_MAX_CONTROL_BYTES = 4096


class CgroupV2Boundary:
    """A unique externally controlled cgroup-v2 worker boundary."""

    def __init__(
        self,
        configuration: WorkerResourceConfiguration,
    ):
        self._configuration = configuration
        self._name = (
            f"gvai-worker-{os.getpid()}-{uuid.uuid4().hex}"
        )
        self._root_fd = -1
        self._group_fd = -1
        self._attached_pid: int | None = None
        self._closed = False

        try:
            self._initialize()
        except Exception:
            self._best_effort_cleanup()
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            ) from None

    @property
    def path(self) -> Path:
        return self._configuration.cgroup_root / self._name

    @property
    def limits(self) -> WorkerResourceLimits:
        return self._configuration.limits

    @property
    def closed(self) -> bool:
        return self._closed

    @staticmethod
    def _open_directory(path: Path) -> int:
        return os.open(
            path,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
        )

    @staticmethod
    def _open_child_directory(
        parent_fd: int,
        name: str,
    ) -> int:
        return os.open(
            name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )

    @staticmethod
    def _read_at(directory_fd: int, name: str) -> str:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        try:
            data = os.read(descriptor, _MAX_CONTROL_BYTES + 1)
        finally:
            os.close(descriptor)

        if len(data) > _MAX_CONTROL_BYTES:
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

        return data.decode("ascii", errors="strict").strip()

    @staticmethod
    def _write_at(
        directory_fd: int,
        name: str,
        value: str,
    ) -> None:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        try:
            pending = memoryview(
                (value.rstrip("\n") + "\n").encode("ascii")
            )
            while pending:
                written = os.write(descriptor, pending)
                if written <= 0:
                    raise OSError("short cgroup control write")
                pending = pending[written:]
        finally:
            os.close(descriptor)

    @staticmethod
    def _secure_directory(status: os.stat_result) -> bool:
        return (
            stat.S_ISDIR(status.st_mode)
            and status.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(status.st_mode) & 0o022 == 0
        )

    def _initialize(self) -> None:
        root = self._configuration.cgroup_root
        expected = os.stat(root, follow_symlinks=False)

        if not self._secure_directory(expected):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

        self._root_fd = self._open_directory(root)
        opened = os.fstat(self._root_fd)

        if (
            opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or not self._secure_directory(opened)
        ):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

        controllers = set(
            self._read_at(
                self._root_fd,
                "cgroup.controllers",
            ).split()
        )
        delegated_controllers = set(
            self._read_at(
                self._root_fd,
                "cgroup.subtree_control",
            ).split()
        )
        if (
            not _REQUIRED_CONTROLLERS.issubset(controllers)
            or not _REQUIRED_CONTROLLERS.issubset(
                delegated_controllers
            )
        ):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

        os.mkdir(self._name, mode=0o700, dir_fd=self._root_fd)
        self._group_fd = self._open_child_directory(
            self._root_fd,
            self._name,
        )

        group_status = os.fstat(self._group_fd)
        if not self._secure_directory(group_status):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

        limits = self._configuration.limits
        self._write_at(
            self._group_fd,
            "memory.max",
            str(limits.memory_max_bytes),
        )
        self._write_at(
            self._group_fd,
            "pids.max",
            str(limits.pids_max),
        )
        self._write_at(
            self._group_fd,
            "cpu.max",
            limits.cpu_max,
        )

        expected_controls = {
            "memory.max": str(limits.memory_max_bytes),
            "pids.max": str(limits.pids_max),
            "cpu.max": limits.cpu_max,
        }
        for name, expected_value in expected_controls.items():
            if self._read_at(self._group_fd, name) != expected_value:
                raise ResourceContainmentError(
                    "private worker resource containment is unavailable"
                )

        # Require the independent whole-cgroup kill mechanism now,
        # before any process can be attached.
        kill_status = os.stat(
            "cgroup.kill",
            dir_fd=self._group_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(kill_status.st_mode):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )

    @staticmethod
    def _process_is_stopped(process_id: int) -> bool:
        try:
            lines = Path(
                f"/proc/{process_id}/status"
            ).read_text(encoding="utf-8").splitlines()
        except OSError:
            return False

        for line in lines:
            if line.startswith("State:"):
                fields = line.split()
                return len(fields) >= 2 and fields[1] in {"T", "t"}
        return False

    def attach_stopped(self, process_id: int) -> None:
        """Attach exactly one process before allowing it to execute."""

        if (
            self._closed
            or self._attached_pid is not None
            or isinstance(process_id, bool)
            or not isinstance(process_id, int)
            or process_id <= 0
            or not self._process_is_stopped(process_id)
        ):
            raise ResourceContainmentError(
                "private worker resource attachment failed"
            )

        try:
            self._write_at(
                self._group_fd,
                "cgroup.procs",
                str(process_id),
            )
            members = {
                int(value)
                for value in self._read_at(
                    self._group_fd,
                    "cgroup.procs",
                ).splitlines()
                if value
            }
        except (OSError, ValueError, UnicodeError):
            raise ResourceContainmentError(
                "private worker resource attachment failed"
            ) from None

        if process_id not in members:
            raise ResourceContainmentError(
                "private worker resource attachment failed"
            )

        self._attached_pid = process_id

    def current_process_count(self) -> int:
        if self._closed:
            raise ResourceContainmentError(
                "private worker resource containment is closed"
            )

        try:
            return int(
                self._read_at(
                    self._group_fd,
                    "pids.current",
                )
            )
        except (OSError, ValueError, UnicodeError):
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            ) from None

    def _is_populated(self) -> bool:
        events = self._read_at(
            self._group_fd,
            "cgroup.events",
        )
        values = {}
        for line in events.splitlines():
            fields = line.split()
            if len(fields) == 2:
                values[fields[0]] = fields[1]
        populated = values.get("populated")
        if populated not in {"0", "1"}:
            raise ResourceContainmentError(
                "private worker resource containment is unavailable"
            )
        return populated == "1"

    def terminate(self, *, timeout: float = 5.0) -> None:
        """Kill every process in the child cgroup and verify emptiness."""

        if self._closed:
            return

        try:
            if self._is_populated():
                self._write_at(self._group_fd, "cgroup.kill", "1")

            deadline = time.monotonic() + timeout
            while self._is_populated():
                if time.monotonic() >= deadline:
                    raise ResourceContainmentError(
                        "private worker resource termination failed"
                    )
                time.sleep(0.01)
        except ResourceContainmentError:
            raise
        except Exception:
            raise ResourceContainmentError(
                "private worker resource termination failed"
            ) from None

    def close(self) -> None:
        """Terminate remaining descendants and remove this exact cgroup."""

        if self._closed:
            return

        failed = False
        try:
            self.terminate()
        except ResourceContainmentError:
            failed = True

        if self._group_fd >= 0:
            os.close(self._group_fd)
            self._group_fd = -1

        try:
            if self._root_fd >= 0:
                os.rmdir(self._name, dir_fd=self._root_fd)
        except OSError:
            failed = True
        finally:
            if self._root_fd >= 0:
                os.close(self._root_fd)
                self._root_fd = -1
            self._closed = True

        if failed:
            raise ResourceContainmentError(
                "private worker resource cleanup failed"
            )

    def _best_effort_cleanup(self) -> None:
        if self._group_fd >= 0:
            try:
                if self._is_populated():
                    self._write_at(
                        self._group_fd,
                        "cgroup.kill",
                        "1",
                    )
            except Exception:
                pass
            os.close(self._group_fd)
            self._group_fd = -1

        if self._root_fd >= 0:
            try:
                os.rmdir(self._name, dir_fd=self._root_fd)
            except OSError:
                pass
            os.close(self._root_fd)
            self._root_fd = -1

        self._closed = True
