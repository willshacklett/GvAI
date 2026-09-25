"""Sanitized preflight: python -m privacy.staging_readiness."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def check_readiness():
    checks = {}

    required = (
        "posix_spawnp", "POSIX_SPAWN_CLOSEFROM", "pidfd_open",
        "killpg", "waitid", "P_PID", "WEXITED", "WNOWAIT", "CLD_EXITED",
        "WSTOPPED", "WNOHANG", "CLD_STOPPED",
    )
    checks["process_api"] = (
        sys.platform == "linux"
        and all(hasattr(os, name) for name in required)
    )

    try:
        from privacy import runtime
        from privacy.encrypted_workspace import WorkspaceAuditLog
        from privacy.filesystem_sandbox import (
            build_filesystem_sandbox_command,
            resolve_filesystem_sandbox_executable,
        )
        from privacy.model_asset_provenance import (
            load_verified_model_assets,
        )
        from privacy.resource_containment import (
            CgroupV2Boundary,
            load_worker_resource_configuration,
        )
    except Exception:
        checks["runtime_import"] = False
        return _report(checks)

    checks["runtime_import"] = True
    checks["private_mode"] = runtime.private_build_enabled()
    checks["encrypted_mode"] = runtime.encrypted_workspace_enabled()

    checks["external_key_provider"] = False
    try:
        key = runtime.load_trusted_workspace_key()
        del key
        checks["key_configuration"] = True
        checks["external_key_provider"] = (
            runtime.WORKSPACE_KEY_SOCKET_ENV in os.environ
            and runtime.ENCRYPTED_WORKSPACE_KEY_ENV not in os.environ
        )
    except Exception:
        checks["key_configuration"] = False

    try:
        verified_model_assets = load_verified_model_assets(
            expected_paths=runtime._filesystem_sandbox_read_paths(),
        )
        del verified_model_assets
        checks["model_asset_provenance"] = True
    except Exception:
        checks["model_asset_provenance"] = False

    try:
        audit_dir = Path(
            os.getenv(runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV)
            or (
                Path(tempfile.gettempdir())
                / "gvai-private-workspace-audit"
            )
        )
        audit_log = WorkspaceAuditLog(
            audit_dir / "audit.jsonl"
        )
        del audit_log
        checks["audit_destination"] = True
    except Exception:
        checks["audit_destination"] = False

    checks["resource_policy"] = False
    checks["resource_containment"] = False
    resource_boundary = None

    try:
        resource_configuration = (
            load_worker_resource_configuration()
        )
        checks["resource_policy"] = True
        resource_boundary = CgroupV2Boundary(
            resource_configuration
        )
        resource_boundary.close()
        checks["resource_containment"] = True
    except Exception:
        checks["resource_containment"] = False
    finally:
        if (
            resource_boundary is not None
            and not getattr(resource_boundary, "closed", True)
        ):
            try:
                resource_boundary.close()
            except Exception:
                checks["resource_containment"] = False

    # Validate syntax only; never execute an operator's model command.
    try:
        from privacy.local_model_worker import _model_command
        _model_command()
        checks["model_command_syntax"] = True
    except Exception:
        checks["model_command_syntax"] = False

    # An override needs its own review; this preflight covers the stock worker.
    checks["stock_worker"] = (
        not os.environ.get(
            "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
            "",
        ).strip()
        and runtime.ENCRYPTED_WORKER_SCRIPT.is_file()
    )
    try:
        resolve_filesystem_sandbox_executable()
        checks["filesystem_sandbox_executable"] = True
    except Exception:
        checks["filesystem_sandbox_executable"] = False

    for name in (
        "network_namespace",
        "mount_namespace",
        "pid_namespace",
        "filesystem_isolation",
    ):
        checks[name] = False

    prerequisites = (
        checks["process_api"]
        and checks["external_key_provider"]
        and checks["stock_worker"]
        and checks["filesystem_sandbox_executable"]
        and checks["model_asset_provenance"]
        and checks["resource_policy"]
        and checks["resource_containment"]
    )

    if prerequisites:
        try:
            namespace_names = ("net", "mnt", "pid")
            parent_namespaces = {
                name: os.readlink(f"/proc/self/ns/{name}")
                for name in namespace_names
            }
            host_root = str(runtime.ROOT)
            host_home = os.path.expanduser("~")

            probe = (
                "import os,socket,sys\n"
                f"parents={parent_namespaces!r}\n"
                "separate=all("
                "os.readlink('/proc/self/ns/'+name)!=parent "
                "for name,parent in parents.items())\n"
                "interfaces={name for _,name in socket.if_nameindex()}\n"
                f"host_hidden=not os.path.exists({host_root!r})\n"
                f"home_hidden=not os.path.exists({host_home!r})\n"
                "private_tmp=os.environ.get('HOME')=='/tmp'\n"
                "sys.exit(0 if ("
                "separate and interfaces <= {'lo'} and host_hidden "
                "and home_hidden and private_tmp"
                ") else 1)\n"
            )

            command = build_filesystem_sandbox_command(
                [sys.executable, "-I", "-c", probe],
                denied_paths=(runtime.ROOT,),
            )
            result = subprocess.run(
                command,
                env={"PATH": os.defpath, "LANG": "C"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                close_fds=True,
            )
            passed = result.returncode == 0
            for name in (
                "network_namespace",
                "mount_namespace",
                "pid_namespace",
                "filesystem_isolation",
            ):
                checks[name] = passed
        except Exception:
            pass

    return _report(checks)


def _report(checks):
    return {
        "scope": "configuration_and_namespace_preflight",
        "ready_for_smoke_test": bool(checks) and all(checks.values()),
        "production_ready": False,
        "checks": {
            name: "pass" if passed else "fail"
            for name, passed in checks.items()
        },
        "not_verified": [
            "configured_model_execution",
            "encrypted_storage_and_audit_round_trip",
            "independently_protected_audit_storage",
            "cross_resource_audit_atomicity",
            "concurrent_host_asset_mutation",
            "production_key_management",
        ],
    }


def main():
    try:
        report = check_readiness()
    except Exception:
        report = _report({"preflight_completed": False})
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ready_for_smoke_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
