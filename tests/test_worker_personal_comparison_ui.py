from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def test_personal_comparison_section_exists():
    html = _html()
    assert 'id="personal-comparison-section"' in html
    assert 'id="personal-comparison-status"' in html
    assert 'id="personal-comparison-content"' in html
    assert "How This Compares With Your Profile" in html


def test_personal_comparison_invitation_state_present_without_profile():
    html = _html()
    assert "Start with your current occupation above to compare your self-reported facts" in html


def test_personal_comparison_uses_post_not_query_params():
    html = _html()
    start = html.index("async function loadPersonalComparison")
    end = html.index("document\n  .getElementById(\"worker-outlook-btn\")", start) if "document\n  .getElementById(\"worker-outlook-btn\")" in html[start:] else start + 4000
    snippet = html[start:end]
    assert 'method: "POST"' in snippet
    assert "/api/worker/personal-comparison" in snippet
    assert "?" not in snippet.split("/api/worker/personal-comparison")[1].split("\n")[0]


def test_personal_comparison_uses_escape_html_for_all_rendered_facts():
    html = _html()
    start = html.index("function renderPersonalComparison")
    end = html.index("async function loadPersonalComparison")
    snippet = html[start:end]
    # every interpolated worker/evidence line must be escaped
    assert "workerLines.map(line => `<li>${escapeHtml(line)}</li>`)" in snippet
    assert "evidenceLines.map(line => `<li>${escapeHtml(line)}</li>`)" in snippet
    assert "escapeHtml(sourceOcc.occupation_title" in snippet
    assert "escapeHtml(targetOcc.occupation_title" in snippet


def test_current_occupation_and_target_both_displayed_distinctly():
    html = _html()
    start = html.index("function renderPersonalComparison")
    end = html.index("async function loadPersonalComparison")
    snippet = html[start:end]
    assert "Current occupation:" in snippet
    assert "Investigated occupation:" in snippet


def test_related_occupation_drilldown_triggers_personal_comparison_and_clears_stale_state():
    html = _html()
    drilldown_start = html.index("async function loadRelatedOccupationDrilldown")
    drilldown_end = html.index("function renderTransitionComparison", drilldown_start)
    drilldown = html[drilldown_start:drilldown_end]
    assert "void loadPersonalComparison(occupationCode, occupationTitle);" in drilldown

    clear_start = html.index("function clearOccupationDrilldown")
    clear_end = html.index("function clearTransitionEvidence", clear_start)
    clear_snippet = html[clear_start:clear_end]
    assert "clearPersonalComparison();" in clear_snippet


def test_clearing_worker_profile_clears_personal_comparison():
    html = _html()
    start = html.index('document.getElementById("clear-worker-profile-btn")')
    end = html.index("const initialWorkerProfile", start)
    snippet = html[start:end]
    assert "clearPersonalComparison();" in snippet


def test_action_plan_links_to_personal_comparison_section():
    html = _html()
    start = html.index("function renderTransitionActionPlan")
    end = html.index("let activePersonalComparisonRequestId")
    snippet = html[start:end]
    assert '#personal-comparison-section' in snippet
    assert "isPersonalCompare" in snippet


def test_no_forbidden_scoring_language_in_personal_comparison_ui_code():
    html = _html()
    start = html.index("function personalComparisonWorkerLines")
    end = html.index("async function loadPersonalComparison")
    snippet = html[start:end].lower()
    for prohibited in ("matched_skills", "skill_gap", "similarity_score", "\"score\"", "\"confidence\""):
        assert prohibited not in snippet
    assert "no personal rating" in html
