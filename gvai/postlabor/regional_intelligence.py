from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from gvai.postlabor.region_intel import (
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
    state_fips = region.get("state_fips")
    county_fips = region.get("county_fips")
    stable_id = (
        f"US:county:{state_fips}{county_fips}" if state_fips and county_fips
        else f"US:state:{state_fips}" if state_fips
        else "US:country" if scope == "country"
        else None
    )
    region_label = (
        f"{region['county']}, {region['state']}" if region.get("county") and region.get("state")
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
    profile = region.get("occupation_profile") or {}
    groups = [{**group, "employed": _number(group.get("employed")),
               "share_percent": _number(group.get("share_percent")) if _number(group.get("employed")) is not None and _number(group.get("share_percent")) is not None and _number(group.get("share_percent")) <= 100 else None}
              for group in profile.get("groups", [])]
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
        "stex": {"status": "available" if stex.get("status") == "known" else "unavailable", "retryable": False},
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
                   "state": region.get("state"), "county": region.get("county"),
                   "state_fips": state_fips, "county_fips": county_fips,
                   "latitude": region.get("latitude"), "longitude": region.get("longitude"),
                   "oews_area_code": region.get("oews_area_code")},
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
    if region.get("supported") and not region.get("oews_area_code"):
        region = {**region, "oews_area_code": resolve_packaged_oews_area_code(region.get("state_fips"), region.get("county_fips"))}
    if region.get("oews_area_code"):
        try:
            stex = _regional_stex_signal(region["oews_area_code"], stex_year=DEFAULT_STEX_SOURCE_YEAR, include_details=True)
        except Exception:
            logger.exception("Packaged regional STEX evidence unavailable")
    return build_regional_intelligence(region, scope=scope, stex_signal=stex)