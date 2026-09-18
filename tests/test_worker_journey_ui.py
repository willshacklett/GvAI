from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def test_first_time_worker_has_a_clear_start_without_empty_evidence_wall():
    html = _html()
    assert 'id="start-worker-profile-btn"' in html
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
    assert "not your current occupation" in html


def test_primary_investigation_is_compact_and_deep_evidence_is_collapsed():
    html = _html()
    assert "Typical local pay" in html
    assert "Jobs in your area" in html
    assert "Career exposure" in html
    assert "Typical preparation" in html
    assert '<details class="worker-deep-evidence">' in html
    assert '<summary>How the work differs</summary>' in html
    assert '<summary>Typical preparation</summary>' in html
    assert '<summary>How this compares with your profile</summary>' in html
    assert "This is not a probability of job loss or percent automatable." in html


def test_worker_request_guards_do_not_share_region_generation_counter():
    html = _html()
    assert "activeWorkerOutlookRequestId" in html
    assert "activeRelatedOccupationsRequestId" in html
    assert "activeDrilldownRequestId" in html
    assert "activeTransitionEvidenceRequestId" in html
    assert "activeTransitionPreparationRequestId" in html


def test_plain_language_and_unknown_states_are_present():
    html = _html()
    assert "Your work and local outlook" in html
    assert "Other occupations to investigate" in html
    assert "Start with your current occupation above" in html
    assert "unknown" in html.lower()
    assert "unavailable, not zero" in html
    assert "Regional OEWS" not in html[html.index("<section class=\"worker-journey\""):html.index("<details id=\"stex-task-audit\"")]


def test_mobile_worker_layout_has_single_column_and_no_fixed_worker_width():
    html = _html()
    assert ".worker-profile-grid { grid-template-columns: 1fr; }" in html
    assert ".worker-summary-grid { grid-template-columns: 1fr; }" in html
    assert "max-height: 70vh" in html
    assert "overflow-wrap: anywhere" in html
