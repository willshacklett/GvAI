"""Explicit user criteria and explainable, evidence-bound decision comparisons."""

import math
import re

VERSION = "gvai.investigation.v1"
TYPES = {
    "worker_opportunity", "relocation", "career_transition", "business_expansion",
    "hiring_workforce", "government_monitoring", "regional_comparison",
}
CRITERIA = {
    "occupations", "workforce_availability", "wage_level", "housing_pressure",
    "labor_force", "distance_radius", "geography", "current_jobs",
    "occupational_composition", "stex", "user_priority",
}
MAX_CANDIDATES = 8
CODE = re.compile(r"[0-9]{2}-[0-9]{4}(?:\.[0-9]{2})?")


def text(value, limit):
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def validate_criteria(criteria):
    if not isinstance(criteria, list) or len(criteria) > len(CRITERIA):
        raise ValueError("Invalid investigation criteria")
    result, keys = [], set()
    for item in criteria:
        if (not isinstance(item, dict) or set(item) != {"key", "value", "direction", "priority"}
                or not isinstance(item["key"], str) or item["key"] not in CRITERIA or item["key"] in keys
                or item["direction"] not in ("lower", "higher", "inspect")
                or item["priority"] not in ("primary", "secondary", "constraint")):
            raise ValueError("Invalid criterion shape")
        key, value = item["key"], item["value"]
        if key == "occupations":
            if not isinstance(value, list) or not 1 <= len(value) <= 5:
                raise ValueError("One to five public occupations required")
            codes = set()
            for occupation in value:
                if (not isinstance(occupation, dict) or set(occupation) != {"code", "workers"}
                        or not isinstance(occupation["code"], str) or not CODE.fullmatch(occupation["code"])
                        or occupation["code"] in codes
                        or isinstance(occupation["workers"], bool)
                        or (occupation["workers"] is not None and
                            (not isinstance(occupation["workers"], int) or not 1 <= occupation["workers"] <= 1000000))):
                    raise ValueError("Invalid public occupation requirement")
                codes.add(occupation["code"])
        elif key == "distance_radius":
            if (not isinstance(value, dict) or set(value) != {"miles", "center"}
                    or isinstance(value["miles"], bool) or not isinstance(value["miles"], (int, float))
                    or not math.isfinite(value["miles"]) or not 1 <= value["miles"] <= 3000
                    or not text(value["center"], 160)):
                raise ValueError("Invalid user radius constraint")
        elif not text(value, 400):
            raise ValueError("Criterion must be bounded user-stated text")
        keys.add(key)
        result.append({"key": key, "value": value, "direction": item["direction"], "priority": item["priority"]})
    return result


def sanitize_investigation(value, known_ids):
    if value is None:
        return None
    if (not isinstance(value, dict) or value.get("schema_version") != VERSION
            or not isinstance(value.get("type"), str) or value["type"] not in TYPES
            or not text(value.get("question"), 1000)):
        raise ValueError("Invalid investigation")
    criteria = validate_criteria(value.get("criteria", []))
    candidates = value.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("Candidate limit exceeded")
    checked, seen = [], set()
    for item in candidates:
        if (not isinstance(item, dict) or not isinstance(item.get("region_id"), str)
                or item["region_id"] not in known_ids or item["region_id"] in seen
                or item.get("status") not in ("candidate", "shortlisted", "rejected")
                or (item.get("reason") is not None and not text(item["reason"], 500))
                or (item.get("status") == "rejected" and not text(item.get("reason"), 500))):
            raise ValueError("Invalid candidate decision")
        seen.add(item["region_id"])
        checked.append({"region_id": item["region_id"], "status": item["status"], "reason": item.get("reason")})
    return {"schema_version": VERSION, "type": value["type"], "question": value["question"],
            "criteria": criteria, "candidates": checked}


def validate_decision_action(action, known_ids):
    kind = action.get("type")
    if kind == "start_investigation":
        return (set(action) == {"type", "investigation_type", "question"}
                and isinstance(action["investigation_type"], str) and action["investigation_type"] in TYPES
                and text(action["question"], 1000))
    if kind == "set_criteria":
        if set(action) != {"type", "criteria"}:
            return False
        try:
            validate_criteria(action["criteria"])
        except (ValueError, TypeError):
            return False
        return True
    if kind in {"remove_candidate", "shortlist_candidate", "focus_candidate"}:
        return set(action) == {"type", "region_id"} and isinstance(action["region_id"], str) and action["region_id"] in known_ids
    if kind == "reject_candidate":
        return (set(action) == {"type", "region_id", "reason"} and isinstance(action["region_id"], str)
                and action["region_id"] in known_ids and text(action["reason"], 500))
    if kind == "compare_candidates":
        return set(action) == {"type"}
    return False


def missing_criteria(investigation):
    if not investigation:
        return ["decision"]
    keys = {item["key"] for item in investigation["criteria"]}
    missing = []
    if "geography" not in keys:
        missing.append("geography")
    if investigation["type"] in {"worker_opportunity", "career_transition", "hiring_workforce", "business_expansion"} and "occupations" not in keys:
        missing.append("occupations")
    if investigation["type"] != "government_monitoring" and not any(
            item["priority"] == "primary" and item["direction"] != "inspect" for item in investigation["criteria"]):
        missing.append("priority")
    return missing


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def assess(investigation, evidence, comparison_ids):
    """Compare stated signals directly: no hidden weights or universal score."""
    result = {"classification": "model_interpretation", "method": "Direct comparisons of stated criteria; no composite score.",
              "missing_criteria": missing_criteria(investigation), "clarification": None,
              "signals": [], "evidence_gaps": [], "status": "gathering", "leader_region_id": None,
              "current_read": "Tell GVAI what decision you are trying to make.", "could_change_if": [],
              "region_reads": {}}
    if not investigation:
        return result
    missing = result["missing_criteria"]
    if missing:
        result["clarification"] = {
            "geography": "Which places or geographic constraints should this decision stay within?",
            "occupations": "Which occupation or public occupation code should we investigate? Broad labor-force totals cannot tell us technician availability.",
            "priority": "Which matters more for your decision: a deeper labor pool, wage level, or housing pressure? Those can point toward different places.",
        }[missing[0]]
    by_id = {model["region"]["id"]: model for model in evidence}
    active = [item["region_id"] for item in investigation["candidates"] if item["status"] != "rejected"]
    ids = [identity for identity in comparison_ids if identity in active] or active
    models = [by_id[identity] for identity in ids if identity in by_id]
    if len(models) < 2:
        result["current_read"] = "Add at least two resolved candidates to examine tradeoffs; no recommendation yet."
    for item in investigation["candidates"]:
        result["region_reads"][item["region_id"]] = {"status": item["status"], "reason": item["reason"],
            "classification": "model_interpretation", "supports": [], "tradeoffs": [],
            "could_move_up": [], "could_eliminate": []}
    regional_signals = {
        "labor_force": ("labor_force", "Published labor-force size; not occupation-specific hiring availability."),
        "housing_pressure": ("home_value_to_income_ratio", "Median home value / household income; not rent or a personal affordability estimate."),
    }
    occupations = next((item["value"] for item in investigation["criteria"] if item["key"] == "occupations"), [])
    for criterion in investigation["criteria"]:
        key = criterion["key"]
        if key in {"geography", "distance_radius"}:
            result["evidence_gaps"].append({"criterion": key,
                "reason": "User-stated search boundary, not verified distance, travel-time or corridor evidence."})
            continue
        if key in {"occupations", "user_priority"}:
            continue
        if key in {"workforce_availability", "wage_level"}:
            if not occupations:
                result["evidence_gaps"].append({"criterion": key, "reason": "Select public occupation codes; aggregate unemployment is not hiring ease."})
                continue
            signal_specs = [(key, occupation["code"]) for occupation in occupations]
        else:
            signal_specs = [(key, None)]
        for _, code in signal_specs:
            values, signatures = [], []
            for model in models:
                identity = model["region"]["id"]
                if key in regional_signals:
                    metric_id, note = regional_signals[key]
                    metric = model.get("metrics", {}).get(metric_id, {})
                    value = metric.get("value") if metric.get("availability") == "available" else None
                    sources = {sid: model.get("sources", {}).get(sid, {}) for sid in metric.get("source_ids", [])}
                    signature = (model["region"].get("type"), tuple((sid, source.get("vintage"), source.get("dataset")) for sid, source in sorted(sources.items())))
                    classification = metric.get("classification")
                    geography = {sid: source.get("geography") for sid, source in sources.items()}
                elif key in {"workforce_availability", "wage_level"}:
                    public = model.get("occupation_evidence_by_code", {}).get(code, {})
                    section = public.get("employment" if key == "workforce_availability" else "wage", {})
                    value = section.get("employment" if key == "workforce_availability" else "median_annual_wage")
                    if (public.get("oews_specificity", {}).get("status") != "exact"
                            or section.get("status") != "known" or not public.get("geography", {}).get("id")):
                        value = None
                    signature = ("oews_labor_market_area", section.get("source_year"), section.get("source"))
                    classification = "source_statistic"
                    sources = {"oews": {"name": section.get("source"), "vintage": section.get("source_year")}}
                    geography = public.get("geography")
                    note = "OEWS occupation employment / wages in a labor-market area, not vacancies, hiring ease or a county estimate."
                else:
                    value, signature, classification, sources, geography = None, None, None, {}, None
                    note = "Jobs, workforce composition and partially audited STEX remain evidence to inspect, not comparable ranking signals."
                signatures.append(signature)
                values.append({"region_id": identity, "value": value if _number(value) else None,
                               "classification": classification, "sources": sources, "geography": geography})
            complete = len(values) >= 2 and all(item["value"] is not None for item in values)
            compatible = complete and len(set(signatures)) == 1 and all(item["sources"] for item in values) and all(
                source.get("vintage") is not None for item in values for source in item["sources"].values())
            if not compatible:
                result["evidence_gaps"].append({"criterion": key, "occupation_code": code,
                    "reason": "Missing evidence, exact occupation match, consistent geography, or matching source vintage; do not rank this signal."})
            preferred = []
            if compatible and criterion["direction"] != "inspect":
                best = (min if criterion["direction"] == "lower" else max)(item["value"] for item in values)
                preferred = [item["region_id"] for item in values if item["value"] == best]
            signal = {"criterion": key, "occupation_code": code, "priority": criterion["priority"],
                      "direction": criterion["direction"], "note": note, "values": values,
                      "comparable": bool(compatible), "preferred_region_ids": preferred}
            result["signals"].append(signal)
            for item in values:
                read = result["region_reads"].get(item["region_id"])
                if read and compatible and criterion["direction"] != "inspect":
                    read["supports" if item["region_id"] in preferred else "tradeoffs"].append({"criterion": key, "occupation_code": code})
                    label = key.replace("_", " ") + (f" ({code})" if code else "")
                    if item["region_id"] not in preferred:
                        read["could_move_up"].append(
                            f"Comparable updated {label} evidence reaches {'at most' if criterion['direction'] == 'lower' else 'at least'} {best}; or you accept this weaker signal as a secondary tradeoff."
                        )
                    elif criterion["priority"] == "primary":
                        read["could_eliminate"].append(
                            f"Comparable updated {label} evidence no longer leads on your primary criterion."
                        )
    primary = [signal for signal in result["signals"] if signal["priority"] == "primary" and signal["direction"] != "inspect"]
    usable = [signal for signal in primary if signal["comparable"]]
    winners = set(ids)
    for signal in usable:
        winners &= set(signal["preferred_region_ids"])
    if investigation["type"] == "government_monitoring":
        result["status"] = "monitoring"
        result["current_read"] = "Watch observed differences and evidence gaps. No time-series change, displacement forecast or policy ranking is established."
    elif len(models) >= 2:
        if usable and len(winners) == 1 and not missing:
            leader = next(iter(winners))
            result["leader_region_id"] = leader
            result["status"] = "provisional"
            gaps = ", ".join(sorted({gap["criterion"].replace("_", " ") for gap in result["evidence_gaps"]}))
            result["current_read"] = (
                f"{by_id[leader]['region'].get('label', leader)} leads only on the comparable primary signals you specified. "
                "This is not a verified hiring-ease, personal affordability or expansion recommendation. "
                + (f"Material unverified signals / constraints: {gaps}. " if gaps else "")
                + "Inspect each candidate's weaker signals before accepting the tradeoff."
            )
        else:
            result["status"] = "tradeoffs" if usable else "insufficient_evidence"
            result["current_read"] = "Primary signals conflict or tie, or criteria/evidence are missing. There is no defensible overall winner yet."
    result["could_change_if"] = [
        "Your primary priority or acceptable tradeoff changes.",
        "Fresh, same-vintage evidence changes a primary signal or closes a material gap.",
        "An exact occupation match contradicts the aggregate labor-pool interpretation.",
    ]
    for gap in result["evidence_gaps"]:
        change = f"Verify {gap['criterion'].replace('_', ' ')}: {gap['reason']}"
        if change not in result["could_change_if"]:
            result["could_change_if"].append(change)
    for read in result["region_reads"].values():
        if read["status"] == "rejected":
            read["could_move_up"].append("You explicitly revisit the recorded rejection reason or acceptable tradeoff.")
        if not read["could_move_up"]:
            read["could_move_up"].append("A material evidence gap closes with favorable comparable evidence for your primary criteria.")
        read["could_eliminate"].append("A verified geographic or other user-stated constraint rules this place out.")
    return result
