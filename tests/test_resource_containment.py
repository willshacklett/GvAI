from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from privacy.resource_containment import (
    CGROUP_ROOT_ENV,
    CgroupV2Boundary,
    CPU_PERIOD_ENV,
    CPU_QUOTA_ENV,
    DEFAULT_CPU_PERIOD_US,
    DEFAULT_CPU_QUOTA_US,
    DEFAULT_MEMORY_MAX_BYTES,
    DEFAULT_PIDS_MAX,
    MEMORY_MAX_ENV,
    PIDS_MAX_ENV,
    ResourceContainmentError,
    build_staged_worker_command,
    load_worker_resource_configuration,
)


def _environment(tmp_path: Path, **values: str) -> dict[str, str]:
    environment = {CGROUP_ROOT_ENV: str(tmp_path)}
    environment.update(values)
    return environment


def test_default_resource_policy(tmp_path):
    configuration = load_worker_resource_configuration(
        _environment(tmp_path)
    )

    assert configuration.cgroup_root == tmp_path.resolve()
    assert (
        configuration.limits.memory_max_bytes
        == DEFAULT_MEMORY_MAX_BYTES
    )
    assert configuration.limits.pids_max == DEFAULT_PIDS_MAX
    assert configuration.limits.cpu_quota_us == DEFAULT_CPU_QUOTA_US
    assert configuration.limits.cpu_period_us == DEFAULT_CPU_PERIOD_US
    assert (
        configuration.limits.cpu_max
        == f"{DEFAULT_CPU_QUOTA_US} {DEFAULT_CPU_PERIOD_US}"
    )


def test_operator_resource_policy_overrides(tmp_path):
    configuration = load_worker_resource_configuration(
        _environment(
            tmp_path,
            **{
                MEMORY_MAX_ENV: str(512 * 1024 * 1024),
                PIDS_MAX_ENV: "32",
                CPU_QUOTA_ENV: "50000",
                CPU_PERIOD_ENV: "100000",
            },
        )
    )

    assert configuration.limits.memory_max_bytes == 512 * 1024 * 1024
    assert configuration.limits.pids_max == 32
    assert configuration.limits.cpu_max == "50000 100000"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (MEMORY_MAX_ENV, "134217727"),
        (MEMORY_MAX_ENV, "1099511627777"),
        (MEMORY_MAX_ENV, "not-a-number"),
        (PIDS_MAX_ENV, "7"),
        (PIDS_MAX_ENV, "4097"),
        (PIDS_MAX_ENV, " 64"),
        (PIDS_MAX_ENV, "+64"),
        (PIDS_MAX_ENV, "64.0"),
        (CPU_PERIOD_ENV, "999"),
        (CPU_PERIOD_ENV, "1000001"),
        (CPU_QUOTA_ENV, "999"),
    ],
)
def test_invalid_resource_values_fail_closed(
    tmp_path,
    name,
    value,
):
    with pytest.raises(
        ResourceContainmentError,
        match="resource configuration is invalid",
    ):
        load_worker_resource_configuration(
            _environment(tmp_path, **{name: value})
        )


def test_cpu_quota_cannot_exceed_aggregate_bound(tmp_path):
    with pytest.raises(ResourceContainmentError):
        load_worker_resource_configuration(
            _environment(
                tmp_path,
                **{
                    CPU_PERIOD_ENV: "1000",
                    CPU_QUOTA_ENV: "129000",
                },
            )
        )


@pytest.mark.parametrize("root", [".", "/"])
def test_unsafe_cgroup_root_fails_closed(root):
    with pytest.raises(ResourceContainmentError):
        load_worker_resource_configuration(
            {CGROUP_ROOT_ENV: root}
        )


def test_noncanonical_cgroup_root_fails_closed(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ResourceContainmentError):
        load_worker_resource_configuration(
            {CGROUP_ROOT_ENV: str(link)}
        )


def test_configuration_errors_do_not_disclose_values(tmp_path):
    secret_value = "RESOURCE-POLICY-SECRET-CANARY"

    with pytest.raises(ResourceContainmentError) as excinfo:
        load_worker_resource_configuration(
            _environment(
                tmp_path,
                **{MEMORY_MAX_ENV: secret_value},
            )
        )

    assert secret_value not in str(excinfo.value)



def test_staged_command_uses_trusted_launcher():
    python = Path(sys.executable).resolve(strict=True)
    worker = [str(python), "-c", "pass"]

    staged = build_staged_worker_command(worker)

    assert staged[0] == str(python)
    assert Path(staged[1]).name == "resource_staging_launcher.py"
    assert Path(staged[1]).is_file()
    assert staged[2:] == worker


@pytest.mark.parametrize(
    "command",
    [
        ["relative-worker"],
        [],
    ],
)
def test_invalid_staged_command_fails_closed(command):
    with pytest.raises(
        ResourceContainmentError,
        match="staging command is invalid",
    ):
        build_staged_worker_command(command)


def test_symlinked_worker_executable_is_rejected(tmp_path):
    link = tmp_path / "python-link"
    link.symlink_to(
        Path(sys.executable).resolve(strict=True)
    )

    with pytest.raises(ResourceContainmentError):
        build_staged_worker_command([str(link), "-c", "pass"])


def test_writable_worker_executable_is_rejected(tmp_path):
    worker = tmp_path / "writable-worker"
    worker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    worker.chmod(0o777)

    with pytest.raises(ResourceContainmentError):
        build_staged_worker_command([str(worker)])


def test_non_cgroup_directory_is_rejected(tmp_path):
    configuration = load_worker_resource_configuration(
        _environment(tmp_path)
    )

    with pytest.raises(
        ResourceContainmentError,
        match="resource containment is unavailable",
    ):
        CgroupV2Boundary(configuration)

    assert list(tmp_path.iterdir()) == []



@pytest.mark.parametrize(
    "delegated",
    [
        "",
        "cpu memory",
        "cpu pids",
        "memory pids",
    ],
)
def test_undelegated_controllers_fail_before_child_creation(
    tmp_path,
    delegated,
):
    (tmp_path / "cgroup.controllers").write_text(
        "cpu memory pids\n",
        encoding="ascii",
    )
    (tmp_path / "cgroup.subtree_control").write_text(
        delegated + "\n",
        encoding="ascii",
    )

    configuration = load_worker_resource_configuration(
        _environment(tmp_path)
    )

    with pytest.raises(
        ResourceContainmentError,
        match="resource containment is unavailable",
    ):
        CgroupV2Boundary(configuration)

    assert not any(
        entry.name.startswith("gvai-worker-")
        for entry in tmp_path.iterdir()
    )


@pytest.mark.parametrize(
    "events",
    [
        "",
        "frozen 0",
        "populated 2",
        "populated unknown",
    ],
)
def test_cgroup_population_state_must_be_explicit(
    monkeypatch,
    events,
):
    boundary = object.__new__(CgroupV2Boundary)
    boundary._group_fd = 123

    monkeypatch.setattr(
        boundary,
        "_read_at",
        lambda directory_fd, name: events,
    )

    with pytest.raises(
        ResourceContainmentError,
        match="resource containment is unavailable",
    ):
        boundary._is_populated()


@pytest.mark.skipif(
    os.getenv("GVAI_RUN_RESOURCE_CONTAINMENT_TEST") != "1",
    reason="real cgroup containment test is opt-in",
)
def test_real_cgroup_boundary_contains_and_kills_tree():
    root = Path(
        os.getenv(CGROUP_ROOT_ENV, "/sys/fs/cgroup")
    ).resolve(strict=True)

    configuration = load_worker_resource_configuration(
        {
            CGROUP_ROOT_ENV: str(root),
            MEMORY_MAX_ENV: str(128 * 1024 * 1024),
            PIDS_MAX_ENV: "8",
            CPU_QUOTA_ENV: "20000",
            CPU_PERIOD_ENV: "100000",
        }
    )

    boundary = None
    process = None
    group_path = None

    child_code = r"""
import os
import signal
import subprocess

os.kill(os.getpid(), signal.SIGSTOP)

descendant = subprocess.Popen(
    ["sleep", "30"],
    start_new_session=True,
)
descendant.wait()
"""

    try:
        boundary = CgroupV2Boundary(configuration)
        group_path = boundary.path

        process = subprocess.Popen(
            [sys.executable, "-c", child_code],
            start_new_session=True,
        )

        deadline = time.monotonic() + 5.0
        stopped = False

        while time.monotonic() < deadline:
            waited_pid, status = os.waitpid(
                process.pid,
                os.WNOHANG | os.WUNTRACED,
            )
            if waited_pid == process.pid and os.WIFSTOPPED(status):
                stopped = True
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)

        assert stopped
        assert process.poll() is None

        boundary.attach_stopped(process.pid)
        assert boundary.current_process_count() == 1

        os.kill(process.pid, signal.SIGCONT)

        deadline = time.monotonic() + 5.0
        while (
            boundary.current_process_count() < 2
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)

        assert boundary.current_process_count() == 2
        assert (
            group_path / "memory.max"
        ).read_text(encoding="ascii").strip() == str(
            128 * 1024 * 1024
        )
        assert (
            group_path / "pids.max"
        ).read_text(encoding="ascii").strip() == "8"
        assert (
            group_path / "cpu.max"
        ).read_text(encoding="ascii").strip() == "20000 100000"

        boundary.close()

        assert boundary.closed
        assert process.wait(timeout=5) == -signal.SIGKILL
        assert not group_path.exists()
    finally:
        if process is not None and process.poll() is None:
            os.kill(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

        if boundary is not None and not boundary.closed:
            boundary.close()

    assert group_path is not None
    assert not group_path.exists()
