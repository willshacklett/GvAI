from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _business_slice():
    html = _html()
    return html[html.index('id="business-workspace"'):html.index('<div class="layer-bar">')]


def test_business_workspace_entry_and_globe_identity_remain():
    html = _html()
    assert 'class="brand-logo"' in html
    assert 'id="open-business-workspace-btn"' in html
    assert 'id="business-workspace" class="business-workspace"' in html
    assert "Business Workforce Intelligence" in html
    assert "Open Business workspace" in html
    assert "Open Laborers workspace" in html


def test_business_workflow_is_region_occupation_evidence():
    business = _business_slice()
    for text in (
        "1. Choose location",
        "2. Choose occupation",
        "3. Review workforce evidence",
        "4. Add to workforce plan",
        "How many workers are employed in this occupation locally?",
        "What does the published wage evidence show?",
        "How specific is the available occupation evidence?",
        "What preparation does the occupation typically require?",
        "What does structural exposure indicate?",
    ):
        assert text in business


def test_business_fetches_canonical_composition_endpoint():
    html = _html()
    assert "/api/business/workforce-intelligence" in html
    assert "loadBusinessWorkforceEvidence" in html
    assert "occupation_code" in html
    assert "lat: String(currentRegionLatitude)" in html
    assert "lon: String(currentRegionLongitude)" in html


def test_business_plan_storage_contract_is_versioned_local_and_bounded():
    html = _html()
    assert 'gvai.businessWorkforcePlan.v1' in html
    assert 'BUSINESS_WORKFORCE_PLAN_VERSION = "v1"' in html
    assert 'BUSINESS_WORKFORCE_PLAN_MAX = 10' in html
    assert "existing.length >= BUSINESS_WORKFORCE_PLAN_MAX" in html
    assert "Employer-selected order is preserved" in html
    assert "persistBusinessPlan([...existing" in html


def test_business_state_is_separate_from_worker_profile_state():
    html = _html()
    start = html.index("function businessSelectedOccupation")
    end = html.index("async function loadSelectedCountyBoundary", start)
    business_js = html[start:end]
    assert "WORKER_PROFILE_STORAGE_KEY" not in business_js
    assert "gvai.workerProfile.v1" not in business_js
    assert "storedWorkerProfile" not in business_js
    assert "workerProfile" not in business_js


def test_business_evidence_cards_preserve_missing_specificity_and_stex_semantics():
    html = _html()
    assert "Unavailable" in html
    assert "unavailable and is never replaced with zero" in html
    assert "broader OEWS category" in html
    assert "STEX is structural exposure evidence" in html
    assert "It is not a probability" in html
    assert "percent automatable" in html
    assert "staffing-reduction recommendation" in html


def test_business_safety_systems_representation_is_truthful_boundary_only():
    business = _business_slice()
    assert "GVAI Safety Systems boundary" in business
    assert "does not copy the separate Safety Systems implementation" in business
    assert "If no external decider is configured" in business
    html = _html()
    assert "does not copy" in html
    assert "active governance" in html


def test_business_workspace_explains_entry_plan_and_provenance():
    html = _html()
    business = _business_slice()
    assert "For business teams" in html
    assert "Review published regional workforce evidence" in html
    assert "Workforce plan <span class=\"business-plan-limit\">(1-10)</span>" in business
    assert "Sources and evidence boundaries" in business
    assert "broader OEWS category" in business
    assert "Add an occupation after reviewing its evidence" in business


def test_business_mobile_layout_stacks_controls_and_plan_cards():
    html = _html()
    mobile = html[html.index("@media (max-width: 900px)"):html.index("@media print")]
    assert ".business-workspace" in mobile
    assert ".business-workflow" in mobile
    assert ".business-control-grid" in mobile
    assert ".business-evidence-grid" in mobile
    assert ".business-plan-facts" in mobile
    assert "min-height: 44px" in mobile


def test_business_workspace_has_no_scores_rankings_or_verdicts():
    business = _business_slice().lower()
    for prohibited in (
        "business score",
        "gvai score",
        "hard to hire",
        "best labor market",
        "hiring recommendation",
        "staffing recommendation",
        "rank occupations",
        "good labor market",
        "bad labor market",
        "strong labor market",
        "weak labor market",
    ):
        assert prohibited not in business
    assert "does not compute a score for businesses" in business
    assert "not a ranking" in business
