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
        "What To Investigate Next",
    ):
        assert stage in html
    assert 'data-worker-stage="my-work"' in html
    assert 'data-worker-stage="local-outlook"' in html
    assert 'data-worker-stage="explore-occupations"' in html
    assert 'data-worker-stage="investigate"' in html
    assert 'data-worker-stage="next-investigation"' in html
    assert "Back to globe" in html


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
