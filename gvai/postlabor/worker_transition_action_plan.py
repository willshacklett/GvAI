"""Deterministic factual next steps for investigating an occupation."""

from __future__ import annotations

from typing import Any, Dict, List

from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    normalize_occupation_code,
)
from gvai.postlabor.worker_region_outlook import (
    synthesize_worker_region_outlook,
)
from gvai.postlabor.worker_transition_evidence import (
    EMPHASIS_SIMILAR,
    synthesize_worker_transition_evidence,
)
from gvai.postlabor.worker_transition_preparation import (
    synthesize_worker_transition_preparation_evidence,
)


def _action(
    action_id: str,
    title: str,
    explanation: str,
    evidence_status: str,
    evidence_source: str,
    *,
    supporting_facts: List[str] | None = None,
    limitation: str | None = None,
) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "title": title,
        "explanation": explanation,
        "evidence_status": evidence_status,
        "evidence_source": evidence_source,
        "supporting_facts": supporting_facts or [],
        "limitation": limitation,
    }


def _preparation_action(preparation: Dict[str, Any]) -> Dict[str, Any] | None:
    target = preparation["target_preparation"]
    job_zone = target["job_zone"]
    education = target["education"]
    facts = []

    if job_zone["status"] == "known":
        facts.append(
            f"{job_zone.get('title') or 'O*NET Job Zone'}"
        )
        for label, value in (
            ("Education", job_zone.get("education")),
            ("Related experience", job_zone.get("related_experience")),
            ("On-the-job training", job_zone.get("job_training")),
        ):
            if value is not None:
                facts.append(f"{label}: {value}")

    if education["status"] == "known":
        levels = education.get("levels") or []
        if levels:
            top_level = max(
                levels,
                key=lambda level: (
                    level.get("percentage_of_respondents") is not None,
                    level.get("percentage_of_respondents") or 0,
                    level.get("title") or "",
                ),
            )
            percentage = top_level.get("percentage_of_respondents")
            if percentage is None:
                facts.append(
                    "O*NET education survey data is available for current workers."
                )
            else:
                facts.append(
                    f"O*NET worker survey: {percentage}% reported "
                    f"{top_level.get('title') or 'this education level'}."
                )

    if not facts:
        return None

    return _action(
        "review_typical_preparation",
        "Review typical preparation",
        "Review O*NET preparation evidence published for the occupation being investigated.",
        "known",
        "O*NET Web Services",
        supporting_facts=facts,
        limitation=(
            "Job Zone and education-survey evidence describe the occupation and "
            "its current workers; they are not requirements or facts about you."
        ),
    )


def _regional_action(
    signal: Dict[str, Any],
    *,
    action_id: str,
    title: str,
    value_fields: List[str],
) -> Dict[str, Any]:
    status = signal["status"]
    if status != "known":
        return _action(
            action_id,
            title,
            signal["explanation"],
            "unavailable",
            "BLS OEWS",
            limitation="Unavailable regional evidence is not a zero value.",
        )

    facts = []
    for field in value_fields:
        value = signal.get(field)
        if value is not None:
            facts.append(f"{field.replace('_', ' ').title()}: {value}")
    if signal.get("source_year") is not None:
        facts.append(f"Source year: {signal['source_year']}")

    limitation = None
    if signal.get("match_specificity") == "broader_category":
        limitation = signal["explanation"]

    return _action(
        action_id,
        title,
        signal["explanation"],
        "known",
        signal.get("source") or "BLS OEWS",
        supporting_facts=facts,
        limitation=limitation,
    )


def _difference_action(evidence: Dict[str, Any]) -> Dict[str, Any] | None:
    labels = {
        "work_activity_comparison": "work activity",
        "skill_comparison": "skill",
        "knowledge_comparison": "knowledge area",
        "ability_comparison": "ability",
    }
    facts = []
    unavailable = []
    for field, label in labels.items():
        comparison = evidence[field]
        if comparison["status"] != "known":
            unavailable.append(label)
            continue
        items = [
            item for item in comparison.get("items") or []
            if item.get("emphasis") != EMPHASIS_SIMILAR
        ]
        if items:
            item = items[0]
            facts.append(
                f"{label.title()}: {item['name']} is {item['emphasis'].replace('_', ' ')}."
            )

    if not facts:
        return None

    limitation = (
        "These are O*NET occupational emphasis differences, not personal "
        "strengths, weaknesses, or gaps."
    )
    if unavailable:
        limitation += " Unavailable comparison evidence: " + ", ".join(unavailable) + "."
    return _action(
        "review_occupational_differences",
        "Review how the work differs",
        "Review areas the investigated occupation emphasizes differently from the current occupation.",
        "known",
        "O*NET Web Services",
        supporting_facts=facts,
        limitation=limitation,
    )


def synthesize_worker_transition_action_plan(
    source_occupation_code: str,
    target_occupation_code: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Dict[str, Any]:
    """Build a fixed-order investigation checklist from factual evidence only."""
    source_code = normalize_occupation_code(source_occupation_code)
    target_code = normalize_occupation_code(target_occupation_code)
    if (latitude is None) != (longitude is None):
        raise ValueError("lat and lon must be provided together.")

    transition_evidence = synthesize_worker_transition_evidence(
        source_code, target_code
    )
    preparation_evidence = synthesize_worker_transition_preparation_evidence(
        source_code, target_code
    )

    actions = []
    preparation_action = _preparation_action(preparation_evidence)
    if preparation_action:
        actions.append(preparation_action)

    region_outlook = None
    if latitude is not None and longitude is not None:
        region_outlook = synthesize_worker_region_outlook(
            latitude, longitude, target_code
        )
        if region_outlook.get("supported"):
            occupation = region_outlook["occupation"]
            actions.append(_regional_action(
                occupation["regional_wage"],
                action_id="compare_local_pay",
                title="Compare local pay",
                value_fields=["median_hourly_wage", "median_annual_wage"],
            ))
            actions.append(_regional_action(
                occupation["regional_employment"],
                action_id="check_local_employment_presence",
                title="Check local employment presence",
                value_fields=["employment"],
            ))

    difference_action = _difference_action(transition_evidence)
    if difference_action:
        actions.append(difference_action)

    actions.append(_action(
        "verify_licensing_or_credentials",
        "Verify licenses or credentials",
        "Check applicable state and local licensing or credential requirements.",
        "unavailable",
        "GVAI coverage limitation",
        limitation=(
            "GVAI does not currently provide authoritative state or local licensing "
            "or credential evidence for this occupation."
        ),
    ))
    actions.append(_action(
        "compare_personal_background_separately",
        "Compare against your own background",
        "Compare this occupation profile with your own experience, education, licenses, and preferences before making a decision.",
        "not_assessed",
        "Worker-provided information",
        limitation=(
            "Occupational evidence does not determine personal qualification or "
            "whether this path is right for you."
        ),
    ))

    return {
        "supported": True,
        "source_occupation_code": source_code,
        "source_occupation_title": transition_evidence["source_occupation_title"],
        "target_occupation_code": target_code,
        "target_occupation_title": transition_evidence["target_occupation_title"],
        "actions": actions,
        "regional_evidence_included": region_outlook is not None,
        "region": region_outlook,
        "explanation": (
            "This is a fixed-order checklist of occupational and regional evidence "
            "to investigate. It is not a recommendation, score, or personal qualification judgment."
        ),
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "synthesize_worker_transition_action_plan",
]