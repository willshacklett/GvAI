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


SOURCE = Path(
    "data/onet/raw/15-1252_00.tasks.json"
)

OUTPUT_DIR = Path(
    "data/stex/ratings/15-1252_00"
)

SUMMARY_PATH = Path(
    "data/stex/occupations/15-1252_00.stex.json"
)

SCORER_ID = "openai-gpt-5.6-sol-stex-v0.1"

BATCH_SCORED_AT_UTC = (
    "2026-09-12T00:10:00+00:00"
)


RATINGS = {
    "21662": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Analyzing user needs, requirements, design feasibility, "
            "time constraints, and cost constraints is primarily "
            "information processing and reasoning over structured and "
            "unstructured project information. Current AI systems can "
            "perform substantial portions of requirements analysis and "
            "feasibility assessment without physical execution. Human "
            "judgment remains valuable for context and accountability, "
            "making strong augmentation likely."
        ),
    },

    "21669": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Software testing, validation procedure development, "
            "programming, and documentation are predominantly digital "
            "activities. Current AI-assisted development systems can "
            "generate tests, code, documentation, and validation plans "
            "and can execute many of these activities inside software "
            "environments. Human review remains important, so strong "
            "augmentation is also likely."
        ),
    },

    "21664": {
        "digital_capability": 3,
        "physical_execution": 0,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Conferencing with technical personnel combines communication, "
            "requirements synthesis, negotiation, and system-design reasoning. "
            "AI can summarize discussions, identify constraints, propose "
            "interfaces, and support technical decisions, but organizational "
            "context and collaborative judgment still favor human involvement."
        ),
    },

    "21670": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Modifying existing software to correct errors, adapt to new "
            "hardware, upgrade interfaces, or improve performance is a "
            "digital software-engineering task. Current AI coding systems "
            "can inspect code, propose and implement changes, generate "
            "patches, and assist debugging without requiring physical "
            "execution."
        ),
    },

    "21673": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Preparing reports and correspondence concerning project "
            "specifications, activities, and status is primarily a language "
            "and information-synthesis task. Current AI systems can draft, "
            "summarize, structure, and revise this material with high "
            "capability."
        ),
    },

    "21661": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Analyzing information and recommending or planning a system "
            "installation or modification is primarily analytical and "
            "planning work. Current AI systems can compare requirements, "
            "constraints, architectures, dependencies, and implementation "
            "options without requiring physical execution."
        ),
    },

    "21676": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Storing, retrieving, manipulating, and analyzing data for "
            "system capability and requirements analysis is natively digital. "
            "Current software and AI systems can perform these operations "
            "directly and at scale."
        ),
    },

    "21667": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Designing, developing, and modifying software using scientific "
            "analysis and mathematical models is primarily digital reasoning "
            "and code production. Current AI systems can contribute directly "
            "to architecture, implementation, mathematical analysis, code "
            "generation, and design evaluation, although human oversight "
            "remains important."
        ),
    },

    "21668": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Determining system performance standards involves requirements "
            "analysis, technical reasoning, benchmarking criteria, and "
            "documentation. These activities can be substantially supported "
            "or performed by current AI and software tools without physical "
            "execution."
        ),
    },

    "21665": {
        "digital_capability": 3,
        "physical_execution": 0,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Consulting with customers or departments combines technical "
            "explanation, status communication, requirements clarification, "
            "and negotiation. AI can support much of the information and "
            "communication work, but trust, accountability, and ambiguous "
            "stakeholder context preserve an important human role."
        ),
    },

    "21663": {
        "digital_capability": 3,
        "physical_execution": 0,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Conferencing with project or data-processing managers is largely "
            "communication and requirements gathering. AI can capture, "
            "summarize, compare, and reason over the information exchanged, "
            "but organizational judgment and collaborative decision-making "
            "still favor human participation."
        ),
    },

    "21671": {
        "digital_capability": 3,
        "physical_execution": 1,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Monitoring equipment or system functioning can often be performed "
            "through telemetry, logs, automated tests, anomaly detection, and "
            "remote diagnostics. Some physical equipment may require on-site "
            "inspection when instrumentation is incomplete, so physical and "
            "human-presence requirements are not zero."
        ),
    },

    "21666": {
        "digital_capability": 3,
        "physical_execution": 1,
        "human_presence_requirement": 1,
        "augmentation_likelihood": 4,
        "rationale": (
            "Coordinating software installation primarily involves planning, "
            "sequencing, communication, configuration, and verification. Much "
            "of the software portion can be automated or remotely executed, "
            "while installations involving hardware or organizational change "
            "may still require people at the site."
        ),
    },

    "21678": {
        "digital_capability": 2,
        "physical_execution": 0,
        "human_presence_requirement": 2,
        "augmentation_likelihood": 3,
        "rationale": (
            "Supervising technical and scientific personnel involves task "
            "tracking, review, communication, coaching, judgment, conflict "
            "resolution, and accountability. AI can assist planning and "
            "review, but present-day organizational supervision retains a "
            "substantial human relationship and responsibility component."
        ),
    },

    "21677": {
        "digital_capability": 2,
        "physical_execution": 0,
        "human_presence_requirement": 2,
        "augmentation_likelihood": 3,
        "rationale": (
            "Assigning and supervising technical work can be supported by "
            "software through scheduling, prioritization, progress monitoring, "
            "and work analysis. Human management remains important for "
            "judgment, accountability, coaching, and interpersonal issues."
        ),
    },

    "21672": {
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 4,
        "rationale": (
            "Evaluating reporting requirements, costs, security needs, and "
            "other factors to determine hardware configuration is primarily "
            "an analytical comparison and recommendation task. Current AI "
            "systems can evaluate specifications, constraints, costs, and "
            "security requirements without physical execution."
        ),
    },

    "21679": {
        "digital_capability": 3,
        "physical_execution": 1,
        "human_presence_requirement": 2,
        "augmentation_likelihood": 4,
        "rationale": (
            "Training users combines explanation, demonstration, feedback, "
            "adaptation to learner needs, and sometimes interaction with "
            "physical equipment. AI tutors and interactive software can "
            "perform substantial instructional functions, but human support "
            "remains important for difficult, contextual, or physical cases."
        ),
    },
}


def main() -> int:
    source = json.loads(
        SOURCE.read_text()
    )

    occupation = source["occupation"]
    vintage = source["source"]["tasks_vintage"]

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_task_ids = {
        task["task_id"]
        for task in source["tasks"]
    }

    rating_task_ids = set(RATINGS)

    if source_task_ids != rating_task_ids:
        missing = sorted(
            source_task_ids - rating_task_ids
        )

        extra = sorted(
            rating_task_ids - source_task_ids
        )

        raise RuntimeError(
            "Rating set does not exactly match "
            "frozen task set. "
            f"Missing={missing}, extra={extra}"
        )

    records = []

    for task in source["tasks"]:
        rating = RATINGS[
            task["task_id"]
        ]

        record = TaskRatingRecord.create(
            occupation_code=(
                occupation["onet_soc_code"]
            ),
            occupation_title=(
                occupation["title"]
            ),
            task_id=task["task_id"],
            task_title=task["title"],
            task_category=task["category"],
            source_importance=(
                task["importance"]
            ),
            source_name=(
                f"O*NET Tasks / "
                f"{vintage['source']}"
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
            scored_at_utc=(
                BATCH_SCORED_AT_UTC
            ),
        )

        output = (
            OUTPUT_DIR
            / f"{task['task_id']}.json"
        )

        output.write_text(
            json.dumps(
                record.to_dict(),
                indent=2,
            )
            + "\n"
        )

        records.append(record)

    result = aggregate_occupation_stex(
        records
    )

    summary = result.to_dict()

    summary["schema_version"] = (
        "gvai.stex.occupation-summary.v0.1"
    )

    summary["source"] = {
        "name": source["source"]["name"],
        "tasks_source": vintage["source"],
        "tasks_year": vintage["year"],
        "onet_soc_code": (
            occupation["onet_soc_code"]
        ),
    }

    summary["scorer_id"] = SCORER_ID

    summary["interpretation"] = (
        "Importance-weighted structural exposure "
        "of rated O*NET task content under STEX "
        "v0.1. This is not a probability of job "
        "loss or the percentage of jobs that can "
        "be automated."
    )

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
        )
        + "\n"
    )

    print(
        "occupation:",
        occupation["title"],
    )

    print(
        "task files:",
        len(records),
    )

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

    print(
        "summary:",
        SUMMARY_PATH,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
