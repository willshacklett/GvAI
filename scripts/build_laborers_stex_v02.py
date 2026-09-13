from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gvai.postlabor.stex import (
    STEX_RUBRIC_V0_2,
    TaskRatingRecord,
    aggregate_occupation_stex,
    calculate_task_exposure,
)
from gvai.postlabor.sources.oews import OEWSClient
from gvai.postlabor.stex.store import list_occupation_stex_profiles

CODE = "53-7062.00"
SAFE_CODE = CODE.replace(".", "_")
SOURCE = Path(f"data/onet/raw/{SAFE_CODE}.tasks.json")
OUTPUT_DIR = Path(f"data/stex/ratings/{SAFE_CODE}")
SUMMARY_PATH = Path(f"data/stex/occupations/{SAFE_CODE}.stex.json")
REPORT_PATH = Path("docs/stex/LABORERS_V0_2_RERATING_REPORT.md")
SCORER_ID = "openai-gpt-5.6-sol-stex-v0.2"
SCORED_AT_UTC = "2026-09-12T00:00:00+00:00"
AREA_CODE = "0034980"
OEWS_YEAR = 2025
FIVE_PROPOSED_CODES = {
    "53-7062.00", "35-3023.00", "41-2031.00", "29-1141.00", "11-1021.00",
}
OLD_PROFILE = {
    "structural_exposure": 14.6242,
    "augmentation_likelihood": 2.5305,
    "rubric_version": "STEX v0.1",
}

# Preserved v0.1 values are used only to make the migration report auditable.
OLD_RATINGS = {
    "10789": (0, 3, 4, 2), "10779": (3, 2, 2, 4), "10781": (0, 4, 4, 2),
    "10788": (0, 3, 4, 2), "10782": (0, 3, 4, 2), "10778": (2, 2, 3, 3),
    "10780": (4, 0, 0, 4), "10790": (0, 4, 4, 2), "10787": (0, 3, 4, 2),
    "10786": (0, 3, 4, 2), "10783": (0, 3, 4, 2), "10792": (2, 4, 3, 3),
    "10796": (2, 2, 3, 3), "1001441": (2, 2, 3, 3),
}

# v0.2 ratings distinguish physical automation capability (P) from human presence (R).
RATINGS = {
    "10789": (2, 3, 1, 3, "Automated storage systems, inventory sensing, and forklifts can protect and organize standardized equipment areas. Human presence remains useful for irregular storage, exceptions, and safety accountability, but is not intrinsic to the task."),
    "10779": (4, 1, 1, 4, "Digital dispatch systems can deliver work orders and convert speech or text instructions into actionable assignments. Human interaction may be needed for ambiguous instructions, but routine assignment interpretation is not inherently human-present."),
    "10781": (1, 4, 1, 3, "Conveyors, autonomous mobile robots, and automated forklifts can move standardized freight through configured routes. Human presence remains relevant for damaged, blocked, or irregular loads and safety exceptions, not for every movement."),
    "10788": (1, 3, 2, 3, "Robotic palletizing and strapping equipment can install protective devices on standardized loads. Irregular freight, damaged packaging, and exception handling retain a moderate human-presence requirement."),
    "10782": (2, 4, 1, 3, "Automated sortation and machine-vision systems can classify and route standardized cargo at scale. Human presence is mainly needed for exceptions, damaged freight, and unstructured items rather than ordinary sorting."),
    "10778": (3, 3, 1, 4, "Print-and-apply labeling, barcode systems, and machine vision can identify and mark standardized containers. Human presence is mainly an exception and accountability function when identifiers or containers are irregular."),
    "10780": (4, 1, 0, 4, "Scanners, RFID, sensors, and warehouse software can record units handled without a person being physically present at each recording event. Human review may address discrepancies, but the recording function itself is digital."),
    "10790": (1, 3, 2, 3, "Powered lifting equipment and robotic load-handling systems can attach or manipulate standardized lifting devices. Human presence remains important for variable rigging, load balance, and safety exceptions, but the task is not universally human-dependent."),
    "10787": (1, 3, 2, 3, "Autonomous carts, mobile robots, and powered vehicles can transport tools or supplies along known routes. Human presence remains useful for selection, obstacles, and irregular retrieval, while routine transport can be automated."),
    "10786": (1, 3, 2, 3, "Robotic packaging systems can pack standardized containers and assist with repacking predictable damage patterns. Irregular damage, materials, and exception decisions retain a moderate human-presence requirement."),
    "10783": (1, 3, 2, 3, "Robotic assembly cells can form standardized containers or crates from prepared components. Variable materials, tool handling, and nonstandard assemblies create human-dependent exceptions without making all assembly inherently human-present."),
    "10792": (2, 3, 1, 3, "Computer-controlled cranes, booms, and camera systems can adjust position and movement from sensor or operator inputs. Human presence is mainly needed for unusual conditions, safety judgment, and exceptions."),
    "10796": (2, 3, 2, 3, "Automated test fixtures and robotic connectors can connect standardized electrical equipment for testing. Human presence remains relevant to nonstandard equipment, safety isolation, and troubleshooting, but not every connection."),
    "1001441": (3, 3, 2, 3, "Machine vision and sensing can identify many standardized damage or leak indicators, while irregular defects and safety-sensitive exceptions need human judgment. The source marks this New task with zero importance, so it remains unrated and excluded from aggregation."),
}


def main() -> int:
    source = json.loads(SOURCE.read_text())
    source_task_ids = {task["task_id"] for task in source["tasks"]}
    if source_task_ids != set(RATINGS):
        raise RuntimeError("v0.2 ratings do not exactly match the frozen task set")

    records = []
    for task in source["tasks"]:
        d, p, r, augmentation, task_rationale = RATINGS[task["task_id"]]
        record = TaskRatingRecord.create(
            occupation_code=source["occupation"]["onet_soc_code"],
            occupation_title=source["occupation"]["title"],
            task_id=task["task_id"],
            task_title=task["title"],
            task_category=task["category"],
            source_importance=task["importance"],
            source_name=f"O*NET Tasks / {source['source']['tasks_vintage']['source']}",
            source_year=source["source"]["tasks_vintage"]["year"],
            digital_capability=d,
            physical_execution=p,
            human_presence_requirement=r,
            augmentation_likelihood=augmentation,
            scorer_id=SCORER_ID,
            rationale=task_rationale,
            scored_at_utc=SCORED_AT_UTC,
            review_status="proposed",
            rubric_version=STEX_RUBRIC_V0_2,
        )
        (OUTPUT_DIR / f"{task['task_id']}.json").write_text(
            json.dumps(record.to_dict(), indent=2) + "\n"
        )
        records.append(record)

    result = aggregate_occupation_stex(records)
    summary = result.to_dict()
    summary.update({
        "schema_version": "gvai.stex.occupation-summary.v0.2",
        "source": {
            "name": source["source"]["name"],
            "tasks_source": source["source"]["tasks_vintage"]["source"],
            "tasks_year": source["source"]["tasks_vintage"]["year"],
            "onet_soc_code": CODE,
        },
        "scorer_id": SCORER_ID,
        "review_status": "proposed",
        "interpretation": (
            "Importance-weighted structural exposure under STEX v0.2. R is "
            "required human presence, not generic physical presence. This is "
            "not a probability of job loss or the percentage of jobs that can "
            "be automated."
        ),
    })
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n")

    # Runtime uses the packaged local OEWS snapshot; this is also an offline
    # calculation for the report and never refreshes BLS data.
    total_employment, employment_rows = OEWSClient().fetch_catalog_regional_employment(
        area_code=AREA_CODE,
        source_year=OEWS_YEAR,
    )
    approved_codes = {
        profile["occupation_code"]
        for profile in list_occupation_stex_profiles()
    }
    employment_by_code = {
        row.occupation_code: row.employment
        for row in employment_rows
    }
    current_covered_employment = sum(
        employment_by_code.get(code, 0.0)
        for code in approved_codes
    )
    laborers_employment = employment_by_code[CODE]
    denominator = total_employment.employment
    laborers_only_projected_employment = (
        current_covered_employment + laborers_employment
    )
    five_profile_projected_employment = current_covered_employment + sum(
        employment_by_code.get(code, 0.0)
        for code in FIVE_PROPOSED_CODES
    )

    lines = [
        "# Laborers STEX v0.2 Re-rating Report",
        "",
        "Status: PROPOSED. This profile remains excluded from production.",
        "",
        f"Old STEX (v0.1): {OLD_PROFILE['structural_exposure']}",
        f"New STEX (v0.2): {result.structural_exposure}",
        f"Old augmentation (v0.1): {OLD_PROFILE['augmentation_likelihood']}",
        f"New augmentation (v0.2): {result.augmentation_likelihood}",
        f"Total importance weight: {result.total_importance_weight}",
        f"Rated/unrated tasks: {result.rated_task_count}/{result.unrated_task_count}",
        "",
        "| Task | Importance | v0.1 D/P/R | v0.2 D/P/R | v0.1 exposure | v0.2 exposure | Weighted contribution | Changed? |",
        "|---|---:|---|---|---:|---:|---:|---|",
    ]
    for record in records:
        old_d, old_p, old_r, old_augmentation = OLD_RATINGS[record.task_id]
        old_exposure = calculate_task_exposure(
            digital_capability=old_d,
            physical_execution=old_p,
            human_presence_requirement=old_r,
        )
        weight = (
            record.source_importance * record.structural_exposure
            / result.total_importance_weight
            if record.importance_status == "rated" else 0.0
        )
        old_tuple = (old_d, old_p, old_r)
        new_tuple = (record.digital_capability, record.physical_execution, record.human_presence_requirement)
        lines.append(
            f"| {record.task_id} {record.task_title} | {record.source_importance:g} | "
            f"{old_tuple} | {new_tuple} | {old_exposure} | "
            f"{record.structural_exposure} | {weight:.4f} | {'yes' if old_tuple != new_tuple or old_augmentation != record.augmentation_likelihood else 'no'} |"
        )
    lines.extend([
        "",
        "The damage/leak inspection task (1001441) remains O*NET importance 0, "
        "importance_status=unrated, and contributes 0 to the weighted result.",
        "",
        f"Current production covered employment: {current_covered_employment:,.0f}",
        f"Laborers employment: {laborers_employment:,.0f}",
        f"Projected covered employment if Laborers alone were approved: {laborers_only_projected_employment:,.0f}",
        f"BLS All Occupations denominator: {denominator:,.0f}",
        f"Current production coverage: {current_covered_employment / denominator * 100:.4f}%",
        f"Laborers incremental coverage: {laborers_employment / denominator * 100:.4f} percentage points",
        f"PROJECTED COVERAGE IF LABORERS ALONE WERE APPROVED: {laborers_only_projected_employment / denominator * 100:.4f}%",
        f"FIVE-PROFILE PROPOSED PREVIEW (NOT LABORERS-ONLY): {five_profile_projected_employment / denominator * 100:.4f}%",
        "These projections are informational only and do not affect production.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "rubric_version": STEX_RUBRIC_V0_2,
        "structural_exposure": result.structural_exposure,
        "augmentation_likelihood": result.augmentation_likelihood,
        "rated_task_count": result.rated_task_count,
        "unrated_task_count": result.unrated_task_count,
        "total_importance_weight": result.total_importance_weight,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
