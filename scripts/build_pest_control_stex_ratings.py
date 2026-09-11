from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gvai.postlabor.stex import (
    TaskRatingRecord,
    aggregate_occupation_stex,
)

SOURCE = Path("data/onet/raw/37-2021_00.tasks.json")
OUTPUT_DIR = Path("data/stex/ratings/37-2021_00")
SUMMARY_PATH = Path(
    "data/stex/occupations/37-2021_00.stex.json"
)

SCORER_ID = "openai-gpt-5.6-sol-stex-v0.1"
BATCH_SCORED_AT_UTC = "2026-09-11T23:30:00+00:00"


RATINGS = {
    "7974": {
        "scored_at_utc": "2026-09-11T23:15:52.354457+00:00",
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 3,
        "rationale": (
            "The task is primarily information recording. Current software "
            "and AI systems can capture, transcribe, structure, summarize, "
            "and store work-activity records with high capability. The "
            "recording function does not itself require physical execution "
            "or a human to be physically present. In current occupational "
            "settings, automation is also likely to augment workers by "
            "reducing documentation effort while humans continue performing "
            "the underlying field work."
        ),
    },

    "7977": {
        "digital_capability": 0,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 1,
        "rationale": (
            "Cleaning a completed pest-control work site is primarily "
            "physical work in variable customer environments. General-purpose "
            "automation has limited present capability in such unstructured "
            "spaces, and under current conditions a human worker is normally "
            "required on site."
        ),
    },

    "20760": {
        "digital_capability": 4,
        "physical_execution": 1,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Area calculations, treatment-volume calculations, and service "
            "estimation are strongly suited to software and AI. Measurement "
            "may still involve field observations, but plans, digital "
            "measurements, sensors, and structured inputs can substantially "
            "reduce the need for physical human execution. The most likely "
            "near-term effect is strong worker augmentation."
        ),
    },

    "7976": {
        "digital_capability": 0,
        "physical_execution": 2,
        "human_presence_requirement": 3,
        "augmentation_likelihood": 2,
        "rationale": (
            "Applying pesticides is a physical task with safety, navigation, "
            "coverage, and environmental constraints. Specialized automated "
            "application systems are plausible in some settings, but "
            "unstructured buildings and field environments substantially "
            "limit general substitution today."
        ),
    },

    "20759": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Generating treatment and prevention recommendations is primarily "
            "an information, diagnosis, and communication task. Current AI "
            "systems can synthesize observations and structured pest data into "
            "recommendations without requiring physical execution. In "
            "practice, expert oversight and customer interaction make strong "
            "augmentation especially likely."
        ),
    },

    "7975": {
        "digital_capability": 3,
        "physical_execution": 1,
        "human_presence_requirement": 3,
        "augmentation_likelihood": 4,
        "rationale": (
            "Inspection combines visual recognition, diagnosis, environmental "
            "reasoning, and physical access to customer property. AI and "
            "computer vision can assist interpretation, but obtaining complete "
            "observations in varied buildings still generally requires an "
            "on-site human under current conditions."
        ),
    },

    "7979": {
        "digital_capability": 0,
        "physical_execution": 3,
        "human_presence_requirement": 3,
        "augmentation_likelihood": 2,
        "rationale": (
            "Vehicle operation has substantial demonstrated automation "
            "capability, but pest-control routes involve public roads, "
            "customer properties, equipment handling, and operational "
            "exceptions. Human supervision or presence remains strongly "
            "required in current commercial deployment."
        ),
    },

    "7978": {
        "digital_capability": 2,
        "physical_execution": 1,
        "human_presence_requirement": 3,
        "augmentation_likelihood": 3,
        "rationale": (
            "Directing or assisting other workers includes coordination, "
            "judgment, communication, and physical participation. AI can "
            "support instructions and workflow coordination, but treatment "
            "work in variable environments still depends heavily on people "
            "present at the site."
        ),
    },

    "7983": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Reviewing reports or diagrams and selecting a treatment approach "
            "is primarily information processing and decision support. Current "
            "AI systems can analyze structured reports, diagrams, prior "
            "treatment information, and rule-based constraints without "
            "requiring physical execution."
        ),
    },

    "7982": {
        "digital_capability": 0,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 1,
        "rationale": (
            "Cutting or boring structural material and injecting pesticide "
            "requires physical access, tools, positioning, safety judgment, "
            "and adaptation to site conditions. Current general automation has "
            "limited capability for this task in customer environments."
        ),
    },

    "7981": {
        "digital_capability": 0,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 1,
        "rationale": (
            "Posting physical warning signs and securing building doors "
            "requires manipulation of the physical environment at the site. "
            "Although parts could theoretically be mechanized, current "
            "commercial practice generally requires an on-site worker."
        ),
    },

    "7985": {
        "digital_capability": 0,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 1,
        "rationale": (
            "Setting traps and placing bait requires access to variable, often "
            "confined or irregular physical locations and manipulation of "
            "materials in the environment. Current general-purpose automation "
            "has limited substitution capability."
        ),
    },

    "7986": {
        "digital_capability": 0,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 1,
        "rationale": (
            "Removing blockages with hand tools is physical work in "
            "unstructured and potentially contaminated environments. Present "
            "automation capability is limited and a human worker is generally "
            "required at the location."
        ),
    },

    "7987": {
        "digital_capability": 1,
        "physical_execution": 1,
        "human_presence_requirement": 4,
        "augmentation_likelihood": 2,
        "rationale": (
            "Positioning tarpaulins, sealing vents, and checking physical "
            "containment requires dexterous manipulation across irregular "
            "building geometry. Sensors and software may assist leak checking, "
            "but the overall task remains strongly dependent on on-site human "
            "execution."
        ),
    },

    "1001584": {
        "digital_capability": 4,
        "physical_execution": 1,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 3,
        "rationale": (
            "Inventory monitoring can be performed through inventory software, "
            "barcode systems, RFID, connected storage systems, or AI-assisted "
            "records. Physical handling may occur elsewhere in the workflow, "
            "but monitoring inventory itself is highly digitally executable. "
            "O*NET currently marks this task as New with importance 0, so it "
            "is preserved as unrated and excluded from weighted aggregation."
        ),
    },
}


def main() -> int:
    source = json.loads(SOURCE.read_text())

    occupation = source["occupation"]
    vintage = source["source"]["tasks_vintage"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    source_task_ids = {
        task["task_id"]
        for task in source["tasks"]
    }

    rating_task_ids = set(RATINGS)

    if source_task_ids != rating_task_ids:
        missing = sorted(source_task_ids - rating_task_ids)
        extra = sorted(rating_task_ids - source_task_ids)

        raise RuntimeError(
            "Rating set does not exactly match frozen task set. "
            f"Missing={missing}, extra={extra}"
        )

    records = []

    for task in source["tasks"]:
        rating = RATINGS[task["task_id"]]

        record = TaskRatingRecord.create(
            occupation_code=occupation["onet_soc_code"],
            occupation_title=occupation["title"],
            task_id=task["task_id"],
            task_title=task["title"],
            task_category=task["category"],
            source_importance=task["importance"],
            source_name=(
                f"O*NET Tasks / {vintage['source']}"
            ),
            source_year=vintage["year"],
            digital_capability=rating[
                "digital_capability"
            ],
            physical_execution=rating[
                "physical_execution"
            ],
            human_presence_requirement=rating[
                "human_presence_requirement"
            ],
            augmentation_likelihood=rating[
                "augmentation_likelihood"
            ],
            scorer_id=SCORER_ID,
            rationale=rating["rationale"],
            scored_at_utc=rating.get(
                "scored_at_utc",
                BATCH_SCORED_AT_UTC,
            ),
        )

        output = OUTPUT_DIR / f"{task['task_id']}.json"

        output.write_text(
            json.dumps(
                record.to_dict(),
                indent=2,
            )
            + "\n"
        )

        records.append(record)

    result = aggregate_occupation_stex(records)

    summary = result.to_dict()
    summary["schema_version"] = (
        "gvai.stex.occupation-summary.v0.1"
    )
    summary["source"] = {
        "name": source["source"]["name"],
        "tasks_source": vintage["source"],
        "tasks_year": vintage["year"],
        "onet_soc_code": occupation["onet_soc_code"],
    }
    summary["scorer_id"] = SCORER_ID
    summary["interpretation"] = (
        "Importance-weighted structural exposure of rated "
        "O*NET task content under STEX v0.1. This is not "
        "a probability of job loss or the percentage of jobs "
        "that can be automated."
    )

    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    print("occupation:", occupation["title"])
    print("task files:", len(records))
    print(
        "rated tasks:",
        result.rated_task_count,
    )
    print(
        "unrated tasks:",
        result.unrated_task_count,
    )
    print(
        "importance weight:",
        result.total_importance_weight,
    )
    print(
        "structural exposure:",
        result.structural_exposure,
    )
    print(
        "augmentation likelihood:",
        result.augmentation_likelihood,
    )
    print("summary:", SUMMARY_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
