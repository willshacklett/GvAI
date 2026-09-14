from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]

SANDBOX = (
    ROOT
    / "privacy"
    / "run_network_sandbox.sh"
)


def _namespace_supported() -> bool:
    if not shutil.which("unshare"):
        return False

    if not shutil.which("ip"):
        return False

    result = subprocess.run(
        [
            "unshare",
            "--user",
            "--map-root-user",
            "--net",
            "sh",
            "-c",
            "ip link set lo up",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    return result.returncode == 0


@pytest.mark.skipif(
    not _namespace_supported(),
    reason=(
        "Linux user/network namespaces "
        "are unavailable in this environment."
    ),
)
def test_private_build_network_boundary(tmp_path):
    audit_path = (
        tmp_path
        / "network-audit.jsonl"
    )

    probe_path = (
        tmp_path
        / "network_probe.py"
    )

    probe_path.write_text(
        textwrap.dedent(
            r'''
            import json
            import os
            import socket
            import threading
            import urllib.request
            from http.server import (
                BaseHTTPRequestHandler,
                ThreadingHTTPServer,
            )
            from pathlib import Path


            AUDIT_PATH = Path(
                os.environ[
                    "GVAI_NETWORK_AUDIT_LOG"
                ]
            )


            def audit_denial(
                *,
                destination,
                protocol,
                reason,
            ):
                record = {
                    "event":
                        "network_egress_denied",
                    "process_id":
                        os.getpid(),
                    "process":
                        "network_probe.py",
                    "destination":
                        destination,
                    "protocol":
                        protocol,
                    "reason":
                        reason,
                }

                with AUDIT_PATH.open(
                    "a",
                    encoding="utf-8",
                ) as handle:
                    handle.write(
                        json.dumps(record)
                        + "\n"
                    )


            class Handler(
                BaseHTTPRequestHandler
            ):
                def do_GET(self):
                    payload = (
                        b'{"model":"gvai-local-mock",'
                        b'"ok":true}'
                    )

                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "application/json",
                    )
                    self.send_header(
                        "Content-Length",
                        str(len(payload)),
                    )
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(
                    self,
                    format,
                    *args,
                ):
                    return


            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                Handler,
            )

            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )

            thread.start()

            port = server.server_address[1]


            # 1. DNS must fail closed.
            try:
                socket.getaddrinfo(
                    "api.openai.com",
                    443,
                )

            except Exception as exc:
                audit_denial(
                    destination=(
                        "api.openai.com:443"
                    ),
                    protocol="dns",
                    reason=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

            else:
                raise AssertionError(
                    "External DNS unexpectedly succeeded"
                )


            # 2. Hostname HTTPS must fail closed.
            try:
                urllib.request.urlopen(
                    "https://api.openai.com/",
                    timeout=2,
                )

            except Exception as exc:
                audit_denial(
                    destination=(
                        "https://api.openai.com/"
                    ),
                    protocol="https",
                    reason=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

            else:
                raise AssertionError(
                    "External hostname HTTPS "
                    "unexpectedly succeeded"
                )


            # 3. Direct-IP egress must fail too.
            try:
                connection = (
                    socket.create_connection(
                        ("1.1.1.1", 443),
                        timeout=2,
                    )
                )

            except Exception as exc:
                audit_denial(
                    destination="1.1.1.1:443",
                    protocol="tcp",
                    reason=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

            else:
                connection.close()

                raise AssertionError(
                    "Direct-IP external connection "
                    "unexpectedly succeeded"
                )


            # 4. Loopback local-model traffic
            # remains usable.
            local_url = (
                f"http://127.0.0.1:{port}/"
            )

            with urllib.request.urlopen(
                local_url,
                timeout=2,
            ) as response:
                body = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            assert response.status == 200
            assert body["ok"] is True
            assert (
                body["model"]
                == "gvai-local-mock"
            )

            server.shutdown()

            print(
                json.dumps({
                    "local_model_ok": True,
                    "local_model_url":
                        local_url,
                    "denials_expected": 3,
                })
            )
            '''
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env[
        "GVAI_NETWORK_AUDIT_LOG"
    ] = str(audit_path)

    result = subprocess.run(
        [
            str(SANDBOX),
            sys.executable,
            str(probe_path),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, (
        "\nSTDOUT:\n"
        + result.stdout
        + "\nSTDERR:\n"
        + result.stderr
    )

    probe_result = json.loads(
        result.stdout.strip().splitlines()[-1]
    )

    assert (
        probe_result["local_model_ok"]
        is True
    )

    records = [
        json.loads(line)
        for line in audit_path
        .read_text(
            encoding="utf-8"
        )
        .splitlines()
        if line.strip()
    ]

    assert len(records) == 3

    destinations = {
        record["destination"]
        for record in records
    }

    assert (
        "api.openai.com:443"
        in destinations
    )

    assert (
        "https://api.openai.com/"
        in destinations
    )

    assert (
        "1.1.1.1:443"
        in destinations
    )

    for record in records:
        assert (
            record["event"]
            == "network_egress_denied"
        )

        assert record["process_id"] > 0
        assert record["process"]
        assert record["destination"]
        assert record["protocol"]
        assert record["reason"]
