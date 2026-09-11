from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gvai.postlabor.sources.onet import (
    ONET_BASE_URL,
    OnetClient,
)


def main() -> int:
    occupation_code = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "37-2021.00"
    )

    client = OnetClient()

    occupation = client.occupation(occupation_code)
    tasks = client.tasks(occupation_code)

    occupation_metadata = client._get(
        f"/online/occupations/{occupation_code}/"
    )

    updated = occupation_metadata.get("updated") or {}
    updated_contents = updated.get("contents") or []

    task_vintage = next(
        (
            {
                "source": item.get("source"),
                "year": item.get("year"),
            }
            for item in updated_contents
            if str(item.get("title") or "").strip().lower()
            == "tasks"
        ),
        None,
    )

    snapshot = {
        "schema_version": "gvai.onet.tasks.v0.1",
        "retrieved_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": {
            "name": "O*NET Web Services",
            "occupation_updated_year": updated.get("year"),
            "tasks_vintage": task_vintage,
            "api_base_url": ONET_BASE_URL,
            "occupation_endpoint": (
                f"{ONET_BASE_URL}/online/occupations/"
                f"{occupation_code}/"
            ),
            "tasks_endpoint": (
                f"{ONET_BASE_URL}/online/occupations/"
                f"{occupation_code}/details/tasks"
            ),
        },
        "occupation": {
            "onet_soc_code": occupation.occupation_code,
            "title": occupation.title,
            "description": occupation.description,
            "bright_outlook": occupation.bright_outlook,
        },
        "task_count": len(tasks),
        "tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "importance": task.importance,
                "category": task.category,
            }
            for task in tasks
        ],
    }

    safe_code = occupation_code.replace(".", "_")
    output = Path(
        f"data/onet/raw/{safe_code}.tasks.json"
    )

    output.write_text(
        json.dumps(
            snapshot,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    print(f"wrote: {output}")
    print(f"occupation: {occupation.title}")
    print(f"task_count: {len(tasks)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
