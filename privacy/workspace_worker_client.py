"""Worker-side JSON-lines client with no trusted workspace state."""

from __future__ import annotations

import base64
import json
import sys
from typing import BinaryIO


class WorkspaceRequestError(RuntimeError):
    pass


class WorkspaceClient:
    """Requests workspace operations over inherited stdin/stdout pipes only."""

    def __init__(
        self,
        input_stream: BinaryIO | None = None,
        output_stream: BinaryIO | None = None,
    ):
        self._input = input_stream or sys.stdin.buffer
        self._output = output_stream or sys.stdout.buffer

    def write_bytes(self, path: str, content: bytes) -> None:
        self._request({
            "operation": "write",
            "path": str(path),
            "content_b64": base64.b64encode(bytes(content)).decode("ascii"),
        })

    def read_bytes(self, path: str) -> bytes:
        response = self._request({
            "operation": "read",
            "path": str(path),
        })
        encoded = response.get("content_b64")
        if not isinstance(encoded, str):
            raise WorkspaceRequestError("workspace operation failed")
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception:
            raise WorkspaceRequestError("workspace operation failed") from None

    def _request(self, payload: dict[str, object]) -> dict[str, object]:
        self._output.write(json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n")
        self._output.flush()
        raw = self._input.readline()
        try:
            response = json.loads(raw.decode("utf-8"))
        except Exception:
            raise WorkspaceRequestError("workspace operation failed") from None
        if not isinstance(response, dict) or response.get("ok") is not True:
            error = response.get("error") if isinstance(response, dict) else None
            if error not in {"workspace request denied", "workspace operation failed"}:
                error = "workspace operation failed"
            raise WorkspaceRequestError(error)
        return response