from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _between(html, start, end):
    start_index = html.index(start)
    return html[start_index:html.index(end, start_index)]


def test_active_investigation_has_versioned_browser_local_contract():
    html = _html()
    assert 'const ACTIVE_INVESTIGATION_STORAGE_KEY = "gvai.activeInvestigation.v1";' in html
    assert 'const ACTIVE_INVESTIGATION_VERSION = "v1";' in html
    contract = _between(html, "function setActiveInvestigation(", "function syncActiveInvestigationRegion()")
    for field in (
        "schema_version",
        "investigated_occupation",
        "originating_occupation",
        "region",
        "navigation_stage",
    ):
        assert field in contract
    for private_field in ("workerProfile", "credentials", "skills", "wage", "mobility", "preferences"):
        assert private_field not in contract


def test_active_investigation_rejects_stale_or_malformed_storage_without_throwing():
    html = _html()
    validator = _between(html, "function isActiveInvestigationV1(", "function loadActiveInvestigationContext()")
    loader = _between(html, "function loadActiveInvestigationContext()", "function persistActiveInvestigationContext()")
    assert "context.schema_version === ACTIVE_INVESTIGATION_VERSION" in validator
    assert "validInvestigationOccupation(context.investigated_occupation)" in validator
    assert "validInvestigationRegion(context.region)" in validator
    assert "Object.hasOwn(WORKER_WORKSPACE_STAGE_LABELS, context.navigation_stage)" in validator
    assert "try {" in loader
    assert "JSON.parse(localStorage.getItem(ACTIVE_INVESTIGATION_STORAGE_KEY))" in loader
    assert "localStorage.removeItem(ACTIVE_INVESTIGATION_STORAGE_KEY)" in loader
    assert "return null;" in loader


def test_selecting_related_occupation_replaces_active_target_before_downstream_loads():
    html = _html()
    drilldown = _between(html, "async function loadRelatedOccupationDrilldown", "function transitionEmphasisLabel")
    assert drilldown.index("setActiveInvestigation(occupationCode, occupationTitle)") < drilldown.index("loadTransitionEvidence")
    assert "loadTransitionPreparation(occupationCode, occupationTitle)" in drilldown
    assert "loadTransitionActionPlan(occupationCode, occupationTitle)" in drilldown
    assert "loadPersonalComparison(occupationCode, occupationTitle)" not in drilldown


def test_saved_occupation_reenters_the_canonical_investigation():
    html = _html()
    listener = _between(
        html,
        '.getElementById("saved-occupations-content")\n  .addEventListener',
        '.getElementById("clear-saved-occupations-btn")',
    )
    assert "loadRelatedOccupationDrilldown(code, title)" in listener
    assert html.count("async function loadRelatedOccupationDrilldown") == 1


def test_personal_comparison_is_explicit_and_uses_active_target_only_when_invoked():
    html = _html()
    listener = _between(
        html,
        '.getElementById("open-personal-comparison-btn")',
        '.getElementById("open-investigation-summary-btn")',
    )
    assert "section.open = true" in listener
    assert "loadPersonalComparison(currentDrilldownCode, currentDrilldownTitle)" in listener
    comparison = _between(html, "async function loadPersonalComparison", "async function loadTransitionActionPlan")
    assert '"/api/worker/personal-comparison"' in comparison
    assert "target_occupation_code: targetCode" in comparison


def test_action_plan_and_live_jobs_share_active_target_and_public_region():
    html = _html()
    action_plan = _between(html, "async function loadTransitionActionPlan", 'document\n  .getElementById("worker-outlook-btn")')
    live_jobs = _between(html, "async function loadLiveJobs", "async function loadRelatedOccupationDrilldown")
    assert "target=${encodeURIComponent(targetCode)}" in action_plan
    assert "currentRegionLatitude" in action_plan and "currentRegionLongitude" in action_plan
    assert "activeInvestigationContext?.investigated_occupation?.occupation_code" in live_jobs
    assert 'params.set("lat", currentRegionLatitude)' in live_jobs
    assert 'params.set("lon", currentRegionLongitude)' in live_jobs
    assert "Worker Profile" not in live_jobs
    assert "storedWorkerProfile" not in live_jobs


def test_refresh_restores_target_region_and_stage_through_canonical_loader():
    html = _html()
    restore = _between(html, "function restoreActiveInvestigation()", "\n\n\ndocument")
    assert "loadActiveInvestigationContext()" in restore
    assert "currentRegionLatitude = restored.region.latitude" in restore
    assert "currentRegionLongitude = restored.region.longitude" in restore
    assert "loadRelatedOccupationDrilldown(currentDrilldownCode, currentDrilldownTitle)" in restore
    assert 'restoredStage === "live-jobs"' in restore
    assert "setWorkerWorkspaceStage(restoredStage, false)" in restore


def test_unavailable_live_jobs_keeps_visible_investigation_context():
    html = _html()
    live_jobs = _between(html, "async function loadLiveJobs", "async function loadRelatedOccupationDrilldown")
    context_write = 'document.getElementById("live-jobs-context").textContent'
    capability_check = 'if (capability && capability.state !== "available")'
    assert live_jobs.index(context_write) < live_jobs.index(capability_check)
    assert "clearOccupationDrilldown" not in live_jobs
    assert "ACTIVE_INVESTIGATION_STORAGE_KEY" not in live_jobs


def test_context_bar_reuses_saved_summary_and_live_jobs_actions():
    html = _html()
    bar = _between(html, 'id="active-investigation-bar"', "</aside>")
    assert "Investigating" not in bar
    assert 'id="active-investigation-save-btn"' in bar
    assert 'data-worker-stage-action="investigation-summary"' in bar
    assert 'data-worker-stage-load="live-jobs"' in bar
    assert "Return to exploration" in bar
    assert "Investigating: ${occupation.occupation_title}" in html


def test_mobile_active_context_and_primary_actions_are_tappable():
    html = _html()
    mobile = _between(html, "@media (max-width: 900px)", "@media print")
    assert ".active-investigation-bar" in mobile
    assert "grid-template-columns: 1fr" in mobile
    assert ".active-investigation-actions" in mobile
    assert "repeat(2, minmax(0, 1fr))" in mobile
    assert "min-height: 44px" in mobile
    assert "white-space: normal" in mobile