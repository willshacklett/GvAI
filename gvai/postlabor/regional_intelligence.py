from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from gvai.postlabor.region_intel import (
    normalize_fips,
    resolve_packaged_oews_area_code,
    resolve_us_aggregate_region,
    resolve_us_region,
)
from gvai.postlabor.region_labor_intelligence import (
    DEFAULT_STEX_SOURCE_YEAR,
    _housing_pressure_signal,
    _labor_availability_signal,
    _regional_stex_signal,
    _workforce_mix_signal,
)


logger = logging.getLogger(__name__)
SCHEMA_VERSION = "gvai.regional-intelligence.v1"


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


def _metric(label, value, unit, source_ids, method, *, derived=False, reason=None):
    return {
        "label": label,
        "value": value,
        "unit": unit,
        "classification": "derived_metric" if derived else "source_statistic",
        "source_ids": source_ids,
        "method": method,
        "availability": "available" if value is not None else "unavailable",
        "reason": reason if value is None else None,
    }


def build_regional_intelligence(region, *, scope="county", stex_signal=None):
    state_fips = normalize_fips(region.get("state_fips")) if scope != "country" else None
    county_fips = normalize_fips(region.get("county_fips"), county=True) if scope == "county" else None
    stable_id = (
        f"US:county:{state_fips}{county_fips}" if scope == "county" and state_fips and county_fips
        else f"US:state:{state_fips}" if scope == "state" and state_fips
        else "US:country" if scope == "country"
        else None
    )
    region_label = (
        f"{region['county']}, {region['state']}" if scope == "county" and region.get("county") and region.get("state")
        else (region.get("country") or "United States") if scope == "country" and region.get("supported")
        else region.get("state") or region.get("name") or f"US state {state_fips}" if scope == "state" and state_fips
        else region.get("state") or region.get("country") or region.get("name")
        or "Selected region"
    )
    year = region.get("acs_year")
    workforce_year = (region.get("occupation_profile") or {}).get("acs_year", year)
    sources = {
        "acs": {
            "name": "U.S. Census Bureau", "dataset": "ACS 5-year detailed tables",
            "vintage": year, "url": "https://www.census.gov/programs-surveys/acs",
            "last_updated": None, "kind": "source_data",
        },
        "workforce": {
            "name": "U.S. Census Bureau", "dataset": "ACS 5-year S2401",
            "vintage": workforce_year,
            "url": f"https://data.census.gov/table/ACSST5Y{workforce_year}.S2401" if workforce_year else "https://www.census.gov/programs-surveys/acs",
            "last_updated": None, "kind": "source_data",
        },
        "oews": {
            "name": "BLS OEWS", "dataset": "Packaged labor-market-area employment snapshot",
            "vintage": None, "url": "https://www.bls.gov/oes/",
            "last_updated": None, "kind": "source_data",
        },
        "stex": {
            "name": "GVAI STEX", "dataset": "Approved occupation task audits",
            "vintage": None, "methodology": "Employment-weighted structural task exposure over audited occupations only",
            "url": None, "last_updated": None, "kind": "gvai_derived_model",
        },
    }
    fields = {
        "population": ("Population", "people", "ACS B01003_001E"),
        "labor_force": ("Civilian labor force", "people", "ACS B23025_003E"),
        "unemployed": ("Unemployed", "people", "ACS B23025_005E"),
        "median_household_income": ("Median household income", "USD", "ACS B19013_001E"),
        "median_home_value": ("Median home value", "USD", "ACS B25077_001E"),
        "median_age": ("Median age", "years", "ACS B01002_001E"),
    }
    metrics = {
        key: _metric(label, _number(region.get(key)), unit, ["acs"], method,
                     reason="Published ACS evidence is unavailable for this selection.")
        for key, (label, unit, method) in fields.items()
    }
    for key, label, unit, method in (
        ("unemployment_rate", "Unemployment rate", "%", "ACS unemployed / civilian labor force times 100"),
        ("home_value_to_income_ratio", "Home value / income", "ratio", "ACS median home value / median household income; not a rent burden measure"),
    ):
        metrics[key] = _metric(label, _number(region.get(key)), unit, ["acs"], method, derived=True,
                               reason="The required ACS baseline is unavailable.")
    requirements = {
        "unemployment_rate": ("labor_force", "unemployed"),
        "home_value_to_income_ratio": ("median_household_income", "median_home_value"),
    }
    for key, (denominator, numerator) in requirements.items():
        if metrics[denominator]["value"] is None or metrics[denominator]["value"] <= 0 or metrics[numerator]["value"] is None:
            metrics[key].update(value=None, availability="unavailable", reason="The required ACS baseline is unavailable.")
        elif metrics[key]["value"] is not None:
            computed = round(metrics[numerator]["value"] / metrics[denominator]["value"] * (100 if key == "unemployment_rate" else 1), 1 if key == "unemployment_rate" else 2)
            if (key == "unemployment_rate" and metrics[numerator]["value"] > metrics[denominator]["value"]) or not math.isclose(metrics[key]["value"], computed):
                metrics[key].update(value=None, availability="unavailable", reason="Derived value does not match the available ACS baseline.")
    profile = region.get("occupation_profile") or {}
    employed_total = _number(profile.get("civilian_employed_16_plus"))
    groups = [{**group, "employed": _number(group.get("employed")),
               "share_percent": round(_number(group["employed"]) / employed_total * 100, 1) if employed_total and _number(group.get("employed")) is not None and _number(group["employed"]) <= employed_total else None}
              for group in profile.get("groups", [])] if profile.get("data_available") else []
    clean_region = {**region, **{key: item["value"] for key, item in metrics.items()},
                    "occupation_profile": {**profile, "groups": groups, "civilian_employed_16_plus": _number(profile.get("civilian_employed_16_plus"))}}
    labor = _labor_availability_signal(clean_region)
    workforce = _workforce_mix_signal(clean_region)
    housing = _housing_pressure_signal(clean_region)
    metrics["labor_availability"] = _metric(
        "Labor availability", labor["classification"] if labor["status"] == "known" else None,
        "classification", ["acs"], "Unemployment thresholds: below 3.5% tight; 3.5-5.5% balanced; above 5.5% available. Not a hiring forecast.",
        derived=True, reason="Unemployment evidence is unavailable.",
    )
    stex = stex_signal or {
        "id": "regional_stex_coverage", "label": "Regional STEX Coverage", "status": "unknown",
        "values": {}, "explanation": "No packaged STEX coverage is available for this geography.",
    }
    stex_values = stex.get("values") or {}
    selected_area = region.get("oews_area_code") if scope == "county" else None
    signal_area = stex_values.get("oews_area_code")
    if scope != "county" or (selected_area and signal_area and selected_area != signal_area):
        stex = {"id": "regional_stex_coverage", "label": "Regional STEX Coverage", "status": "unknown", "values": {},
                "explanation": "No matching packaged STEX denominator exists for this selected geography."}
        stex_values = {}
        signal_area = None
    for source in ("acs", "workforce"):
        sources[source]["geography"] = {"type": scope, "id": stable_id, "label": region_label}
    sources["oews"]["geography"] = {"type": "oews_labor_market_area", "id": selected_area or signal_area,
        "label": f"OEWS labor-market area {selected_area or signal_area}" if selected_area or signal_area else "OEWS labor-market area (identifier unavailable)"}
    sources["oews"]["vintage"] = stex_values.get("source_year")
    for key, label, field, unit, method in (
        ("stex_coverage", "STEX audit coverage", "coverage_percentage", "%", "Audited covered employment / OEWS total employment times 100; unrated employment remains unknown"),
        ("automation_exposure", "Audited structural exposure", "covered_occupation_stex", "STEX points", "Employment-weighted STEX across audited covered occupations only; not percent automatable or probability of job loss"),
        ("stex_covered_employment", "STEX-covered employment", "stex_covered_employment", "jobs", "Employment in audited occupation rows; labor-market area, not county boundaries"),
        ("total_employment", "OEWS reference employment", "total_employment", "jobs", "OEWS All Occupations labor-market-area employment denominator"),
    ):
        value = _number(stex_values.get(field)) if stex.get("status") == "known" else None
        if key == "automation_exposure" and not (_number(stex_values.get("stex_covered_employment")) or 0):
            value = None
        metrics[key] = _metric(label, value, unit, ["oews", "stex"] if key != "total_employment" else ["oews"], method,
                               derived=key != "total_employment", reason=stex.get("explanation"))
    reference = metrics["total_employment"]["value"]
    covered = metrics["stex_covered_employment"]["value"]
    coverage = metrics["stex_coverage"]["value"]
    if reference is None or reference <= 0 or covered is None or covered > reference:
        for key in ("stex_coverage", "automation_exposure"):
            metrics[key].update(value=None, availability="unavailable", reason="A valid matching OEWS denominator and audited employment are required.")
    elif coverage is not None and not math.isclose(coverage, round(covered / reference * 100, 4), abs_tol=0.0001):
        metrics["stex_coverage"].update(value=None, availability="unavailable", reason="Audit coverage does not match its employment denominator.")
    exposure = metrics["automation_exposure"]["value"]
    if exposure is not None and exposure > 100:
        metrics["automation_exposure"].update(value=None, availability="unavailable", reason="Structural exposure is outside the STEX rubric range.")
    for key, label in (
        ("stability_index", "Post-Labor Stability Index"),
        ("job_displacement", "Job displacement estimate"),
        ("industry_concentration", "Industry concentration index"),
        ("economic_resilience", "Economic resilience index"),
    ):
        metrics[key] = _metric(label, None, "index", [], "No validated regional calculation is connected to this public experience.",
                               derived=True, reason="Unavailable: no supported regional methodology.")
    has_data = any(item["value"] is not None for item in metrics.values())
    retryable = bool(region.get("supported")) and region.get("reason") != "CENSUS_API_KEY is not configured."
    sections = {
        "acs": {"status": "available" if any(metrics[key]["value"] is not None for key in fields) else "unavailable", "retryable": retryable},
        "workforce": {"status": "available" if workforce["status"] == "known" else "unavailable", "retryable": retryable},
        "stex": {"status": "available" if metrics["stex_coverage"]["value"] is not None else "unavailable", "retryable": False},
        "jobs": {"status": "not_requested", "retryable": False, "reason": "Choose an occupation and use the existing live jobs search; regional vacancy totals are not available."},
        "stability": {"status": "unavailable", "retryable": False, "reason": metrics["stability_index"]["reason"]},
    }
    signals = [labor, workforce, housing, stex]
    summary_parts = [signal["explanation"] for signal in signals if signal["status"] == "known"]
    return {
        "schema_version": SCHEMA_VERSION,
        "region": {"id": stable_id, "type": scope, "label": region_label,
                   "country": (region.get("country") or "United States") if region.get("supported") else region.get("country"),
                   "country_code": "US" if region.get("supported") else region.get("country_code"),
                   "state": region.get("state") if scope != "country" else None, "county": region.get("county") if scope == "county" else None,
                   "state_fips": state_fips, "county_fips": county_fips,
                   "latitude": region.get("latitude"), "longitude": region.get("longitude"),
                   "oews_area_code": selected_area},
        "metrics": metrics, "workforce_mix": workforce["values"].get("groups", []),
        "signals": signals, "sources": sources,
        "jobs": {"status": "not_requested", "classification": "source_statistic", "result_count": None,
             "method": "Provider listing results for an explicit occupation/search, not total regional vacancies.",
             "source_names": [], "retrieved_at": None, "last_updated": None},
        "stex": {"contributing_audited_occupations": stex_values.get("contributing_audited_occupations", []),
             "recommended_unaudited_occupations": stex_values.get("recommended_unaudited_occupations", [])},
        "summary": f"{region_label}: " + "; ".join(summary_parts) if summary_parts else f"Some published values are available for {region_label}; interpret each source separately." if has_data else f"Regional evidence is unavailable for {region_label}.",
        "availability": {"status": "partial" if has_data and any(sections[key]["status"] != "available" for key in ("acs", "workforce", "stex")) else "available" if has_data else "unavailable", "sections": sections},
        "freshness": {"retrieved_at": datetime.now(timezone.utc).isoformat(), "source_last_updated": None, "note": "Retrieval time is not the source publication or update date."},
        "stability_components": {"labor": metrics["labor_availability"], "housing": metrics["home_value_to_income_ratio"], "structural_exposure": metrics["automation_exposure"], "composite_available": False},
        "constraints": [signal["explanation"] for signal in signals if signal["status"] != "known"],
    }


def synthesize_regional_intelligence(*, scope="county", latitude=None, longitude=None, state_fips=None):
    if scope == "county":
        region = resolve_us_region(latitude=latitude, longitude=longitude, request_timeout=7)
    else:
        region = resolve_us_aggregate_region(scope=scope, state_fips=state_fips, request_timeout=7)
    stex = None
    if scope == "county" and region.get("supported") and not region.get("oews_area_code"):
        region = {**region, "oews_area_code": resolve_packaged_oews_area_code(region.get("state_fips"), region.get("county_fips"))}
    if scope == "county" and region.get("oews_area_code"):
        try:
            stex = _regional_stex_signal(region["oews_area_code"], stex_year=DEFAULT_STEX_SOURCE_YEAR, include_details=True)
        except Exception:
            logger.exception("Packaged regional STEX evidence unavailable")
    return build_regional_intelligence(region, scope=scope, stex_signal=stex)


def sanitize_regional_context(context):
    def fields(value, allowed, lists=()):
        if not isinstance(value, dict):
            raise ValueError("Invalid structured region context")
        result = {}
        for key in allowed:
            if key not in value:
                continue
            item = value[key]
            if key in lists:
                if not isinstance(item, list) or not all(isinstance(entry, str) for entry in item):
                    raise ValueError("Invalid region context list")
            elif isinstance(item, (dict, list)):
                raise ValueError("Invalid region context scalar")
            result[key] = item
        return result

    metric_fields = ("label", "value", "unit", "classification", "source_ids", "method", "availability", "reason")
    metric_ids = ("population", "labor_force", "unemployed", "median_household_income", "median_home_value", "median_age",
                  "unemployment_rate", "home_value_to_income_ratio", "labor_availability", "stex_coverage", "automation_exposure",
                  "stex_covered_employment", "total_employment", "stability_index", "job_displacement", "industry_concentration", "economic_resilience")
    metrics = context.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Invalid region context metrics")
    result = {"audience": context["audience"], "schema_version": context.get("schema_version"),
              "region": fields(context.get("region"), ("id", "type", "label", "country", "country_code", "state", "county", "state_fips", "county_fips", "latitude", "longitude", "oews_area_code")),
              "metrics": {key: fields(metrics[key], metric_fields, ("source_ids",)) for key in metric_ids if key in metrics}}
    sources = context.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Invalid region context sources")
    result["sources"] = {}
    for key in ("acs", "workforce", "oews", "stex"):
        if key not in sources:
            continue
        source = fields(sources[key], ("name", "dataset", "vintage", "url", "last_updated", "kind", "methodology"))
        if "geography" in sources[key]:
            source["geography"] = fields(sources[key]["geography"], ("type", "id", "label"))
        result["sources"][key] = source
    availability = context.get("availability", {})
    result["availability"] = fields(availability, ("status",))
    sections = availability.get("sections", {})
    if not isinstance(sections, dict):
        raise ValueError("Invalid region context availability")
    result["availability"]["sections"] = {key: fields(sections[key], ("status", "retryable", "reason"))
        for key in ("acs", "workforce", "stex", "jobs", "stability") if key in sections}
    if context.get("stex") is not None:
        stex = context["stex"]
        if not isinstance(stex, dict):
            raise ValueError("Invalid region context STEX")
        result["stex"] = {key: fields(stex[key], metric_fields, ("source_ids",)) for key in ("coverage", "audited_exposure") if key in stex}
    if context.get("jobs") is not None:
        jobs = context["jobs"]
        result["jobs"] = fields(jobs, ("status", "classification", "result_count", "method", "source_names", "retrieved_at", "last_updated", "occupation_code", "occupation_title"), ("source_names",))
        if "search_context" in jobs:
            result["jobs"]["search_context"] = fields(jobs["search_context"], ("location", "latitude", "longitude", "country_code", "radius", "remote_only", "schedule_type_code", "posted_within_days"))
    return result