from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def test_first_time_worker_has_a_clear_start_without_empty_evidence_wall():
    html = _html()
    assert 'id="start-worker-profile-btn"' in html
    assert 'id="open-laborers-workspace-btn"' in html
    assert 'id="laborers-workspace" class="laborers-workspace"' in html
    assert "Start with my current occupation" in html
    assert 'id="worker-profile-card" class="worker-profile-card" aria-labelledby="worker-profile-title" hidden' in html
    assert "GVAI uses your occupation and region to show local labor evidence" in html


def test_returning_worker_profile_is_browser_local_and_current_is_authoritative():
    html = _html()
    assert "gvai.workerProfile.v1" in html
    assert "Edit my work profile" in html
    assert "Clear Profile" in html
    assert "savedProfile?.current_occupation?.occupation_code" in html
    assert "Your saved profile remains your current occupation" in html
    comparison_line = html[html.index("/api/worker/personal-comparison"):].splitlines()[0]
    assert "?" not in comparison_line


def test_current_and_investigated_occupations_have_distinct_context_labels():
    html = _html()
    assert "Your current work" in html
    assert "You're investigating" in html
    assert 'id="current-occupation-context"' in html
    assert 'id="investigated-occupation-context"' in html
    assert 'id="workspace-current-occupation-context"' in html
    assert 'id="workspace-investigated-occupation-context"' in html
    assert "not your current occupation" in html


def test_primary_investigation_is_compact_and_deep_evidence_is_collapsed():
    html = _html()
    assert "Typical local pay" in html
    assert "Jobs in your area" in html
    assert "Career exposure" in html
    assert "Typical preparation" in html
    assert '<details class="worker-deep-evidence">' in html
    assert '<summary>Occupation evidence</summary>' in html
    assert '<summary>Preparation commonly reported for this occupation</summary>' in html
    assert '<summary>How this compares with your profile</summary>' in html
    assert "This is not a probability of job loss or percent automatable." in html


def test_laborers_workspace_has_worker_journey_stages():
    html = _html()
    for stage in (
        "My Work",
        "My Local Outlook",
        "Explore Occupations",
        "Investigate",
        "Investigation Summary",
        "What To Investigate Next",
    ):
        assert stage in html
    assert 'data-worker-stage="my-work"' in html
    assert 'data-worker-stage="local-outlook"' in html
    assert 'data-worker-stage="explore-occupations"' in html
    assert 'data-worker-stage="investigate"' in html
    assert 'data-worker-stage="investigation-summary"' in html
    assert 'data-worker-stage="next-investigation"' in html
    assert "Back to globe" in html


def test_investigation_summary_reuses_existing_investigation_evidence():
    html = _html()
    assert 'id="investigation-summary-content"' in html
    assert 'id="open-investigation-summary-btn"' in html
    assert 'id="print-investigation-summary-btn"' in html
    assert "const investigationSummaryState" in html
    assert "investigationSummaryState.drilldown = data" in html
    assert "investigationSummaryState.transitionEvidence = data" in html
    assert "investigationSummaryState.preparation = data" in html
    assert "investigationSummaryState.personalComparison = data" in html
    assert "investigationSummaryState.actionPlan = data" in html
    assert "renderTransitionActionPlan(actions, !!storedWorkerProfile())" in html


def test_investigation_summary_sources_and_missing_states_are_explicit():
    html = _html()
    summary_start = html.index("function investigationSummaryEmptyState")
    summary_end = html.index("async function loadRelatedOccupations", summary_start)
    summary = html[summary_start:summary_end]
    for source in (
        "O*NET occupation identity",
        "BLS OEWS regional employment and wage evidence",
        "STEX/GVAI audited profile",
        "O*NET Job Zone and education survey",
        "Self-reported Worker Profile",
        "Existing Transition Action Plan evidence",
    ):
        assert source in summary
    assert "No occupation is being investigated yet" in summary
    assert "Explore Occupations" in summary
    assert "Saved Occupations" in summary
    assert "unavailable, not zero" in summary
    assert "unknown" in summary.lower()


def test_investigation_summary_preserves_evidence_boundaries():
    html = _html()
    summary_start = html.index("function oewsSpecificityText")
    summary_end = html.index("async function loadRelatedOccupations", summary_start)
    summary = html[summary_start:summary_end]
    assert "currentDrilldownCode" in summary
    assert "isOccupationSaved(currentDrilldownCode)" in summary
    assert "Broader OEWS category" in summary
    assert "Exact OEWS occupation evidence" in summary
    assert "not a probability of job loss or percent automatable" in summary
    assert "O*NET Job Zone" in summary
    assert "Work activities" in summary
    assert "Skills" in summary
    assert "Knowledge" in summary
    assert "Abilities" in summary
    assert "Self-reported" in summary
    assert "Published evidence" in summary


def test_investigation_summary_privacy_and_escaping_contract():
    html = _html()
    summary_start = html.index("function investigationSummaryEmptyState")
    summary_end = html.index("async function loadRelatedOccupations", summary_start)
    summary = html[summary_start:summary_end]
    assert "localStorage.setItem" not in summary
    assert "fetch(" not in summary
    assert "/api/worker/personal-comparison" not in summary
    assert "JSON.stringify" not in summary
    assert "escapeHtml(title)" in summary
    assert "items.map(item => `<li>${escapeHtml(item)}</li>`)" in summary
    assert "window.print()" in html


def test_investigation_summary_does_not_add_composite_or_verdict_language():
    html = _html().lower()
    summary = html[html.index("function investigationsummaryemptystate"):html.index("async function loadrelatedoccupations")]
    for prohibited in (
        "gvai score",
        "transition score",
        "fit score",
        "readiness score",
        "opportunity score",
        "recommendation score",
        "traffic-light",
        "best occupation",
        "ranking",
        "probability of success",
        "good match",
        "poor match",
        "easy transition",
    ):
        assert prohibited not in summary
    assert "50" not in summary
    assert "mystery neutral" not in summary


def test_saved_occupation_storage_remains_metadata_only_with_summary():
    html = _html()
    start = html.index("function saveOccupation")
    end = html.index("function removeSavedOccupation", start)
    save_snippet = html[start:end]
    assert "occupation_code" in save_snippet
    assert "occupation_title" in save_snippet
    assert "saved_at" in save_snippet
    for evidence_key in ("regional_wage", "regional_employment", "stex", "workerProfile", "transitionEvidence"):
        assert evidence_key not in save_snippet


def test_worker_request_guards_do_not_share_region_generation_counter():
    html = _html()
    assert "activeWorkerOutlookRequestId" in html
    assert "activeRelatedOccupationsRequestId" in html
    assert "activeDrilldownRequestId" in html
    assert "activeTransitionEvidenceRequestId" in html
    assert "activeTransitionPreparationRequestId" in html


def test_plain_language_and_unknown_states_are_present():
    html = _html()
    assert "Your local outlook" in html
    assert "Jobs to explore" in html
    assert "Other occupations to investigate" in html
    assert "Start with your current occupation above" in html
    assert "unknown" in html.lower()
    assert "unavailable, not zero" in html
    assert "Regional OEWS" not in html[html.index("<section class=\"worker-journey\""):html.index("<details id=\"stex-task-audit\"")]


def test_mobile_worker_layout_has_single_column_and_no_fixed_worker_width():
    html = _html()
    assert ".worker-profile-grid { grid-template-columns: 1fr; }" in html
    assert ".worker-summary-grid { grid-template-columns: 1fr; }" in html
    assert ".laborers-stage-grid {\n        grid-template-columns: 1fr;\n      }" in html
    assert ".laborers-stage-nav {\n        grid-template-columns: 1fr;\n      }" in html
    assert "max-height: 70vh" in html
    assert "overflow-wrap: anywhere" in html


def test_no_prohibited_worker_recommendation_language_added():
    html = _html().lower()
    workspace = html[html.index('<main id="laborers-workspace"'):html.index('<div class="layer-bar"')]
    for prohibited in (
        "optimal",
        "best career",
        "recommended career",
        "match score",
        "good fit",
        "bad fit",
        "easy transition",
        "hard transition",
        "you qualify",
        "you do not qualify",
    ):
        assert prohibited not in workspace
