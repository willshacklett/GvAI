from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gvai.postlabor.stex import TaskRatingRecord, aggregate_occupation_stex


SCORER_ID = "openai-gpt-5.6-sol-stex-v0.1"
BATCH_SCORED_AT_UTC = "2026-09-12T00:00:00+00:00"


# Explicit task-level audit decisions: D, P, R, augmentation.
RATINGS = {
    "53-7062.00": {
        "10789": (0, 3, 4, 2),
        "10779": (3, 2, 2, 4),
        "10781": (0, 4, 4, 2),
        "10788": (0, 3, 4, 2),
        "10782": (0, 3, 4, 2),
        "10778": (2, 2, 3, 3),
        "10780": (4, 0, 0, 4),
        "10790": (0, 4, 4, 2),
        "10787": (0, 3, 4, 2),
        "10786": (0, 3, 4, 2),
        "10783": (0, 3, 4, 2),
        "10792": (2, 4, 3, 3),
        "10796": (2, 2, 3, 3),
        "1001441": (2, 2, 3, 3),
    },
    "35-3023.00": {
        "23100": (4, 1, 1, 4),
        "23110": (2, 3, 3, 3),
        "23104": (4, 1, 1, 4),
        "23103": (4, 1, 1, 4),
        "23099": (3, 1, 2, 4),
        "23105": (1, 3, 3, 3),
        "23108": (3, 2, 2, 4),
        "23102": (0, 3, 4, 2),
        "23109": (2, 3, 3, 3),
        "23107": (0, 3, 4, 2),
        "23106": (1, 3, 3, 3),
        "23115": (1, 3, 3, 3),
        "23113": (1, 3, 3, 3),
        "23121": (0, 3, 4, 2),
        "23111": (0, 3, 4, 2),
        "23101": (0, 3, 4, 2),
        "23123": (2, 2, 3, 3),
        "23118": (2, 1, 3, 3),
        "23122": (0, 3, 4, 2),
        "23120": (1, 3, 3, 3),
        "23116": (1, 3, 3, 3),
        "23114": (3, 1, 2, 3),
        "23119": (3, 1, 2, 4),
        "23125": (2, 2, 3, 3),
        "23117": (1, 3, 3, 3),
        "23112": (0, 3, 4, 2),
        "23124": (1, 2, 3, 3),
        "1001532": (2, 2, 3, 3),
    },
    "41-2031.00": {
        "694": (3, 1, 3, 4),
        "700": (3, 1, 3, 4),
        "697": (4, 1, 1, 4),
        "712": (1, 3, 3, 3),
        "701": (3, 1, 2, 4),
        "696": (3, 1, 2, 4),
        "706": (3, 1, 3, 4),
        "702": (3, 1, 3, 4),
        "703": (1, 3, 3, 3),
        "711": (3, 2, 2, 4),
        "708": (1, 3, 3, 3),
        "699": (2, 1, 3, 3),
        "705": (3, 1, 2, 4),
        "707": (0, 3, 4, 2),
        "698": (4, 0, 0, 4),
        "695": (4, 1, 1, 4),
        "704": (4, 0, 1, 4),
        "714": (3, 1, 2, 4),
        "709": (1, 2, 3, 3),
        "710": (1, 2, 3, 3),
        "713": (3, 1, 2, 4),
        "716": (3, 1, 2, 4),
        "717": (3, 1, 2, 4),
        "715": (2, 1, 2, 3),
    },
    "29-1141.00": {
        "1841": (4, 1, 1, 4),
        "20413": (2, 2, 4, 3),
        "1839": (4, 0, 0, 4),
        "1840": (4, 1, 1, 4),
        "1855": (2, 3, 4, 3),
        "1843": (3, 1, 2, 4),
        "1846": (2, 1, 3, 3),
        "1845": (2, 2, 3, 3),
        "1850": (3, 1, 2, 4),
        "1842": (3, 1, 3, 4),
        "1857": (3, 2, 2, 3),
        "1848": (2, 1, 3, 3),
        "1849": (3, 2, 3, 4),
        "1865": (3, 1, 3, 4),
        "1847": (2, 2, 4, 3),
        "1861": (3, 1, 2, 3),
        "1844": (3, 1, 3, 4),
        "1859": (3, 1, 4, 3),
        "1860": (3, 1, 2, 4),
        "1851": (1, 3, 4, 2),
        "1854": (1, 3, 4, 2),
        "1862": (3, 1, 2, 4),
        "1863": (3, 1, 2, 4),
        "1856": (2, 3, 4, 3),
        "1864": (3, 1, 2, 4),
        "1852": (3, 1, 3, 4),
        "1866": (3, 1, 2, 4),
    },
    "11-1021.00": {
        "20699": (4, 0, 2, 4),
        "933": (3, 1, 2, 4),
        "20700": (3, 1, 2, 4),
        "20701": (3, 1, 2, 4),
        "20703": (4, 0, 2, 4),
        "20706": (3, 1, 2, 4),
        "20705": (2, 1, 3, 3),
        "20704": (3, 0, 2, 4),
        "20702": (3, 1, 2, 4),
        "20708": (2, 2, 3, 3),
        "20707": (4, 0, 2, 4),
        "944": (2, 2, 3, 3),
        "945": (3, 0, 2, 4),
        "947": (3, 0, 2, 4),
        "19501": (3, 1, 2, 3),
        "949": (2, 1, 2, 3),
        "948": (2, 1, 2, 3),
    },
}


def rationale(task_title: str) -> str:
    return (
        "Explicit STEX v0.1 audit of the task statement: rate the strongest "
        "current digital or physical execution channel, then apply the "
        "human-presence constraint. Augmentation is retained separately. "
        f"Task statement audited: {task_title}"
    )


def main() -> int:
    for code, ratings in RATINGS.items():
        safe_code = code.replace(".", "_")
        source_path = Path(f"data/onet/raw/{safe_code}.tasks.json")
        output_dir = Path(f"data/stex/ratings/{safe_code}")
        summary_path = Path(f"data/stex/occupations/{safe_code}.stex.json")

        source = json.loads(source_path.read_text())
        source_task_ids = {task["task_id"] for task in source["tasks"]}
        if source_task_ids != set(ratings):
            raise RuntimeError(
                f"Rating set does not exactly match frozen task set for {code}."
            )

        occupation = source["occupation"]
        vintage = source["source"]["tasks_vintage"]
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        records = []

        for task in source["tasks"]:
            digital, physical, presence, augmentation = ratings[task["task_id"]]
            record = TaskRatingRecord.create(
                occupation_code=occupation["onet_soc_code"],
                occupation_title=occupation["title"],
                task_id=task["task_id"],
                task_title=task["title"],
                task_category=task["category"],
                source_importance=task["importance"],
                source_name=f"O*NET Tasks / {vintage['source']}",
                source_year=vintage["year"],
                digital_capability=digital,
                physical_execution=physical,
                human_presence_requirement=presence,
                augmentation_likelihood=augmentation,
                scorer_id=SCORER_ID,
                rationale=rationale(task["title"]),
                scored_at_utc=BATCH_SCORED_AT_UTC,
                review_status="proposed",
            )
            (output_dir / f"{task['task_id']}.json").write_text(
                json.dumps(record.to_dict(), indent=2) + "\n"
            )
            records.append(record)

        result = aggregate_occupation_stex(records)
        summary = result.to_dict()
        summary.update({
            "schema_version": "gvai.stex.occupation-summary.v0.1",
            "source": {
                "name": source["source"]["name"],
                "tasks_source": vintage["source"],
                "tasks_year": vintage["year"],
                "onet_soc_code": occupation["onet_soc_code"],
            },
            "scorer_id": SCORER_ID,
            "review_status": "proposed",
            "interpretation": (
                "Importance-weighted structural exposure of rated O*NET task "
                "content under STEX v0.1. This is not a probability of job "
                "loss or the percentage of jobs that can be automated."
            ),
        })
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        print(
            occupation["onet_soc_code"],
            occupation["title"],
            "tasks", len(records),
            "rated", result.rated_task_count,
            "unrated", result.unrated_task_count,
            "stex", result.structural_exposure,
            "augmentation", result.augmentation_likelihood,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())