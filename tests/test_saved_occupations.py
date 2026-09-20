from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _fn(html, start_marker, end_marker):
    start = html.index(start_marker)
    end = html.index(end_marker, start)
    return html[start:end]


def test_saved_occupations_use_versioned_local_storage_schema():
    html = _html()
    assert 'const SAVED_OCCUPATIONS_STORAGE_KEY = "gvai.savedOccupations.v1";' in html
    assert 'const SAVED_OCCUPATIONS_VERSION = "v1";' in html
    assert "function isSavedOccupationRecord(record)" in html
    assert "schema_version === SAVED_OCCUPATIONS_VERSION" in html


def test_save_occupation_writes_minimal_record_and_dedupes():
    html = _html()
    snippet = _fn(html, "function saveOccupation(", "function removeSavedOccupation(")
    assert "occupation_code" in snippet
    assert "occupation_title" in snippet
    assert "saved_at" in snippet
    assert "filter(record => record.occupation_code !== occupationCode)" in snippet
    # no evidence fields are ever part of a saved record
    for prohibited in ("stex", "oews", "wage", "transition_evidence", "regional_employment"):
        assert prohibited not in snippet.lower()


def test_remove_saved_occupation_only_removes_selected_record():
    html = _html()
    snippet = _fn(html, "function removeSavedOccupation(", "function clearSavedOccupations(")
    assert "next = loadSavedOccupations().filter(record => record.occupation_code !== occupationCode)" in snippet
    assert "persistSavedOccupations(next)" in snippet


def test_clear_saved_occupations_requires_confirmation():
    html = _html()
    assert 'window.confirm("Remove all saved occupations from this browser/device?")' in html
    listener = _fn(html, 'getElementById("clear-saved-occupations-btn")', "renderSavedOccupations();\n\nrenderWorkerOutlookAvailability")
    assert "clearSavedOccupations()" in listener


def test_load_saved_occupations_recovers_from_malformed_local_storage():
    html = _html()
    snippet = _fn(html, "function loadSavedOccupations()", "function persistSavedOccupations(")
    assert "try {" in snippet
    assert "JSON.parse(raw)" in snippet
    assert "if (!Array.isArray(parsed)) return [];" in snippet
    assert "filter(isSavedOccupationRecord)" in snippet
    # any parse failure or storage access failure returns an empty list, never throws
    assert snippet.count("return [];") >= 3


def test_saved_occupation_list_never_stores_evidence_payloads():
    html = _html()
    record_shape = _fn(html, "function isSavedOccupationRecord(record)", "function loadSavedOccupations()")
    for prohibited in ("stex", "oews", "onet_profile", "wage", "transition", "employment"):
        assert prohibited not in record_shape.lower()


def test_worker_profile_clearing_does_not_touch_saved_occupations():
    html = _html()
    snippet = _fn(html, 'document.getElementById("clear-worker-profile-btn")', "const initialWorkerProfile")
    assert "SAVED_OCCUPATIONS_STORAGE_KEY" not in snippet
    assert "removeSavedOccupation" not in snippet
    assert "clearSavedOccupations" not in snippet


def test_closing_investigation_does_not_clear_saved_occupations():
    html = _html()
    snippet = _fn(html, "function clearOccupationDrilldown(", "function clearTransitionEvidence()")
    assert "SAVED_OCCUPATIONS_STORAGE_KEY" not in snippet
    assert "removeSavedOccupation" not in snippet
    assert "clearSavedOccupations" not in snippet
    assert "localStorage.removeItem(ACTIVE_INVESTIGATION_STORAGE_KEY)" in snippet


def test_changing_current_occupation_does_not_delete_saved_occupations():
    html = _html()
    snippet = _fn(html, 'getElementById(\n    "stex-occupation-select"\n  )', "loadOccupationSTEXCatalog();")
    assert "SAVED_OCCUPATIONS_STORAGE_KEY" not in snippet
    assert "removeSavedOccupation" not in snippet
    assert "clearSavedOccupations" not in snippet


def test_reopening_saved_occupation_uses_existing_investigation_flow():
    html = _html()
    delegation = _fn(html, '.getElementById("saved-occupations-content")\n  .addEventListener', '.getElementById("clear-saved-occupations-btn")')
    assert "void loadRelatedOccupationDrilldown(code, title);" in delegation
    # no second/duplicate drilldown implementation was introduced
    assert html.count("async function loadRelatedOccupationDrilldown") == 1
    assert "async function loadSavedOccupationDrilldown" not in html
    assert "async function investigateSavedOccupation" not in html


def test_save_button_reflects_current_investigated_occupation():
    html = _html()
    assert 'id="save-occupation-btn"' in html
    assert 'id="save-occupation-status"' in html
    drilldown = _fn(html, "async function loadRelatedOccupationDrilldown", "function renderTransitionComparison")
    assert "renderSaveOccupationButton(occupationCode, occupationTitle);" in drilldown
    assert "renderSaveOccupationButton(data.occupation_code || occupationCode, data.occupation_title || occupationTitle);" in drilldown


def test_saved_occupations_workspace_area_has_empty_and_populated_states():
    html = _html()
    assert 'data-worker-stage-target="saved-occupations"' in html
    assert 'data-worker-stage="saved-occupations"' in html
    assert "Saved Occupations" in html
    render_fn = _fn(html, "function renderSavedOccupations()", "function formatSavedAt(")
    assert "No saved occupations yet." in render_fn
    assert "Continue investigation" in render_fn
    assert "saved-occupation-remove-btn" in render_fn
    assert "most recently saved first" in render_fn


def test_no_recommendation_or_ranking_language_in_saved_occupations_code():
    html = _html()
    saved_start = html.index("const SAVED_OCCUPATIONS_STORAGE_KEY")
    saved_end = html.index("const WORKER_PROFILE_STORAGE_KEY")
    saved_module = html[saved_start:saved_end].lower()
    workspace_html = _fn(html, 'id="worker-stage-saved-occupations"', "</section>").lower()
    # the only allowed use of "recommendation" is the explicit disclaimer that
    # saving is NOT a recommendation; no promotional/ranking language is allowed
    assert saved_module.count("recommend") == 1
    assert "not a recommendation" in saved_module
    assert workspace_html.count("recommend") == 1
    assert "not a recommendation" in workspace_html
    for prohibited in (
        "best",
        "better fit",
        "strongest",
        "good fit",
        "top pick",
        "score",
        "rank",
    ):
        assert prohibited not in saved_module
        assert prohibited not in workspace_html


def test_saved_occupation_rendering_escapes_title_and_code():
    html = _html()
    render_fn = _fn(html, "function renderSavedOccupations()", "function formatSavedAt(")
    assert "escapeHtml(record.occupation_title" in render_fn
    assert "escapeHtml(record.occupation_code)" in render_fn


def test_no_server_persistence_added_for_saved_occupations():
    html = _html()
    assert html.count("gvai.savedOccupations.v1") >= 1
    api_source = (ROOT / "gvai/api_service.py").read_text()
    assert "saved_occupation" not in api_source.lower()
    assert "/api/worker/saved" not in api_source
