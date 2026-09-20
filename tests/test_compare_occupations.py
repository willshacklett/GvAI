from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _fn(html, start_marker, end_marker):
    start = html.index(start_marker)
    end = html.index(end_marker, start)
    return html[start:end]


def _between(html, start, end):
    start_index = html.index(start)
    return html[start_index:html.index(end, start_index)]


# --- Reuses Saved Occupations as the canonical shortlist source ---

def test_compare_selection_is_a_pointer_into_saved_occupations_not_a_second_store():
    html = _html()
    assert 'const COMPARE_OCCUPATIONS_STORAGE_KEY = "gvai.compareOccupations.v1";' in html
    assert 'const COMPARE_OCCUPATIONS_VERSION = "v1";' in html
    record_shape = _fn(html, "function isCompareSelectionRecord(record)", "function loadCompareSelection()")
    assert "occupation_code" in record_shape
    # no evidence, wage, employment, stex, or title fields are ever stored here
    for prohibited in ("stex", "oews", "wage", "employment", "transition", "occupation_title"):
        assert prohibited not in record_shape.lower()


def test_saved_occupations_stage_offers_compare_selection_controls():
    html = _html()
    stage = _fn(html, 'id="worker-stage-saved-occupations"', "</section>")
    assert 'id="compare-selection-bar"' in stage
    assert 'id="compare-selection-status"' in stage
    assert 'id="open-compare-occupations-btn"' in stage
    assert 'data-worker-stage-action="compare-occupations"' in stage
    assert 'data-worker-stage-load="compare-occupations"' in stage


def test_render_saved_occupations_exposes_compare_toggle_per_item():
    html = _html()
    render_fn = _fn(html, "function renderSavedOccupations()", "function formatSavedAt(")
    assert "compare-toggle-btn" in render_fn
    assert "Add to compare" in render_fn
    assert "Remove from compare" in render_fn
    assert "renderCompareSelectionBar();" in render_fn


def test_removing_or_clearing_saved_occupations_also_drops_compare_selection():
    html = _html()
    remove_fn = _fn(html, "function removeSavedOccupation(", "function clearSavedOccupations(")
    assert "removeFromCompareSelection(occupationCode);" in remove_fn
    clear_fn = _fn(html, "function clearSavedOccupations(", "function renderSaveOccupationButton(")
    assert "persistCompareSelection([]);" in clear_fn


def test_compare_load_drops_selection_codes_no_longer_saved():
    html = _html()
    loader = _fn(html, "async function loadCompareOccupations()", 'document\n  .getElementById("compare-occupations-content")')
    assert "loadSavedOccupations()" in loader
    assert "savedByCode.has(record.occupation_code)" in loader
    assert "persistCompareSelection(items.map(item =>" in loader


# --- Selection / deselection ---

def test_toggle_compare_selection_adds_and_removes():
    html = _html()
    toggle_fn = _fn(html, "function toggleCompareSelection(occupationCode)", "function renderCompareSelectionBar()")
    assert 'existing.filter(record => record.occupation_code !== occupationCode)' in toggle_fn
    assert "renderSavedOccupations();" in toggle_fn


def test_saved_occupations_click_listener_dispatches_compare_toggle():
    html = _html()
    listener = _fn(html, '.getElementById("saved-occupations-content")\n  .addEventListener', '.getElementById("clear-saved-occupations-btn")')
    assert "compare-toggle-btn" in listener
    assert "toggleCompareSelection(code)" in listener


# --- 2-5 occupation bound ---

def test_compare_selection_is_bounded_between_two_and_five():
    html = _html()
    assert "const COMPARE_OCCUPATIONS_MIN = 2;" in html
    assert "const COMPARE_OCCUPATIONS_MAX = 5;" in html
    toggle_fn = _fn(html, "function toggleCompareSelection(occupationCode)", "function renderCompareSelectionBar()")
    assert "existing.length < COMPARE_OCCUPATIONS_MAX" in toggle_fn
    bar_fn = _fn(html, "function renderCompareSelectionBar()", "const WORKER_PROFILE_STORAGE_KEY")
    assert "count < COMPARE_OCCUPATIONS_MIN" in bar_fn
    loader = _fn(html, "async function loadCompareOccupations()", 'document\n  .getElementById("compare-occupations-content")')
    assert "items.length < COMPARE_OCCUPATIONS_MIN" in loader


def test_add_to_compare_button_disabled_at_max_when_not_already_selected():
    html = _html()
    render_fn = _fn(html, "function renderSavedOccupations()", "function formatSavedAt(")
    assert "compareCodes.size >= COMPARE_OCCUPATIONS_MAX" in render_fn


# --- Neutral, deterministic ordering (never a ranking) ---

def test_compare_selection_preserves_worker_selection_order():
    html = _html()
    toggle_fn = _fn(html, "function toggleCompareSelection(occupationCode)", "function renderCompareSelectionBar()")
    # New selections are appended, never re-sorted by any evidence field.
    assert "[...existing, { schema_version: COMPARE_OCCUPATIONS_VERSION, occupation_code: occupationCode }]" in toggle_fn
    for prohibited in (".sort(", "sortBy", "orderBy"):
        assert prohibited not in toggle_fn
    loader = _fn(html, "async function loadCompareOccupations()", 'document\n  .getElementById("compare-occupations-content")')
    for prohibited in (".sort(", "sortBy", "orderBy"):
        assert prohibited not in loader


# --- Factual comparison fields and unknown-stays-unknown ---

def test_unknown_evidence_never_becomes_zero_or_neutral():
    html = _html()
    compare_module = _between(html, "function compareRegionNote(region)", "function formatImportanceValue")
    for phrase in (
        "unavailable for this occupation",
        "select a public region to see regional evidence",
        "select your current occupation to compare",
        "unknown.",
    ):
        assert phrase.lower() in compare_module.lower()
    # unknown facts are never rendered as a numeric zero or a neutral 50.
    assert '": 0"' not in compare_module
    assert "50" not in compare_module


def test_wage_evidence_reuses_canonical_region_outlook_and_formatter():
    html = _html()
    fact_fn = _fn(html, "function compareWageFact(wage, regionNote)", "function comparePreparationFact(")
    assert "formatWageText(wage)" in fact_fn
    assert "suppressed by BLS (unavailable, not zero)" in fact_fn
    assert "broader_category" in fact_fn


def test_employment_evidence_reuses_canonical_region_outlook_and_formatter():
    html = _html()
    fact_fn = _fn(html, "function compareEmploymentFact(employment, regionNote)", "function compareWageFact(")
    assert "formatCompact(employment.employment)" in fact_fn
    assert "broader_category" in fact_fn


def test_stex_semantics_are_structural_exposure_not_probability_or_percent():
    html = _html()
    fact_fn = _fn(html, "function compareStexFact(occupation, regionNote)", "function compareEmploymentFact(")
    assert "Structural exposure:" in fact_fn
    assert "Not a probability of job loss or percent automatable." in fact_fn
    skeleton_fn = _fn(html, "function compareOccupationCardSkeleton(record)", "async function loadCompareOccupationCard")
    assert "STEX is structural exposure evidence, not a probability of job loss or percent automatable." in skeleton_fn


def test_preparation_and_training_evidence_reuse_canonical_job_zone():
    html = _html()
    prep_fn = _fn(html, "function comparePreparationFact(jobZone)", "function compareTrainingFact(")
    assert "Job Zone" in prep_fn
    assert "jobZone.education" in prep_fn
    training_fn = _fn(html, "function compareTrainingFact(jobZone)", "function compareTransitionFact(")
    assert "jobZone.related_experience" in training_fn
    assert "jobZone.job_training" in training_fn
    card_loader = _fn(html, "async function loadCompareOccupationCard", "async function loadCompareOccupations()")
    assert "/api/worker/transition-preparation?source=" in card_loader
    assert "preparation.target_preparation" in card_loader


def test_transition_evidence_reuses_canonical_transition_evidence_endpoint():
    html = _html()
    fact_fn = _fn(html, "function compareTransitionFact(evidence)", "function compareLiveJobsFact(")
    assert "work_activity_comparison" in fact_fn
    card_loader = _fn(html, "async function loadCompareOccupationCard", "async function loadCompareOccupations()")
    assert "/api/worker/transition-evidence?source=" in card_loader


def test_live_jobs_capability_is_checked_once_per_country_not_per_saved_occupation():
    html = _html()
    loader = _fn(html, "async function loadCompareOccupations()", 'document\n  .getElementById("compare-occupations-content")')
    assert loader.count("fetchLiveJobsCapability(") == 1
    assert "liveJobsCapability" in loader


# --- No composite score / ranking / recommendation ---

def test_compare_module_contains_no_composite_or_ranking_vocabulary():
    html = _html()
    compare_module = _between(html, "function compareRegionNote(region)", "function formatImportanceValue").lower()
    for prohibited in (
        "gvai score",
        "opportunity score",
        "fit score",
        "readiness score",
        "weighted average",
        "best occupation",
        "good fit",
        "bad fit",
        "top pick",
        "star rating",
        "green light",
        "red flag",
    ):
        assert prohibited not in compare_module
    # "score" and "rank" are not used anywhere in the comparison logic itself.
    assert "score" not in compare_module
    assert "ranking" not in compare_module or "not a ranking" in compare_module


def test_compare_stage_markup_states_factual_not_ranking():
    html = _html()
    stage = _fn(html, 'id="worker-stage-compare-occupations"', "</section>")
    assert "factual comparison" in stage.lower()
    assert "not a ranking or recommendation" in stage.lower()


# --- Investigation / Live Jobs handoff (no forked systems) ---

def test_compare_investigate_action_reuses_canonical_drilldown_loader():
    html = _html()
    listener = _fn(html, '.getElementById("compare-occupations-content")\n  .addEventListener', "function formatImportanceValue")
    assert "void loadRelatedOccupationDrilldown(code, title);" in listener
    assert html.count("async function loadRelatedOccupationDrilldown") == 1
    assert "async function loadCompareInvestigation" not in html


def test_compare_live_jobs_action_reuses_canonical_live_jobs_loader():
    html = _html()
    listener = _fn(html, '.getElementById("compare-occupations-content")\n  .addEventListener', "function formatImportanceValue")
    assert "setActiveInvestigation(code, title);" in listener
    assert "void loadLiveJobs();" in listener
    assert html.count("async function loadLiveJobs") == 1
    assert "async function loadCompareLiveJobs" not in html


def test_compare_card_region_uses_same_public_region_context_as_canonical_flow():
    html = _html()
    loader = _fn(html, "async function loadCompareOccupations()", 'document\n  .getElementById("compare-occupations-content")')
    assert "publicRegionContext()" in loader
    card_loader = _fn(html, "async function loadCompareOccupationCard", "async function loadCompareOccupations()")
    assert "region.latitude" in card_loader
    assert "region.longitude" in card_loader


# --- Refresh / browser-local behavior and malformed state ---

def test_compare_selection_persists_only_in_local_storage():
    html = _html()
    persist_fn = _fn(html, "function persistCompareSelection(records)", "function isOccupationInCompareSelection(")
    assert "localStorage.setItem(COMPARE_OCCUPATIONS_STORAGE_KEY" in persist_fn
    api_source = (ROOT / "gvai/api_service.py").read_text()
    assert "compare_occupation" not in api_source.lower()
    assert "/api/worker/compare" not in api_source


def test_load_compare_selection_recovers_from_malformed_local_storage():
    html = _html()
    loader = _fn(html, "function loadCompareSelection()", "function persistCompareSelection(")
    assert "try {" in loader
    assert "JSON.parse(raw)" in loader
    assert "if (!Array.isArray(parsed)) return [];" in loader
    assert "filter(isCompareSelectionRecord)" in loader
    assert loader.count("return [];") >= 3


# --- Worker Profile isolation ---

def test_compare_module_never_reads_worker_profile():
    html = _html()
    compare_module = _between(html, "function compareRegionNote(region)", "function formatImportanceValue")
    assert "storedWorkerProfile" not in compare_module
    assert "WORKER_PROFILE_STORAGE_KEY" not in compare_module
    assert "workerProfileFromForm" not in compare_module


def test_compare_live_jobs_search_context_excludes_worker_profile():
    live_jobs = _between(_html(), "async function loadLiveJobs", "async function loadRelatedOccupationDrilldown")
    assert "Worker Profile" not in live_jobs
    assert "storedWorkerProfile" not in live_jobs


# --- Mobile structure ---

def test_compare_occupations_grid_is_single_column_on_mobile():
    html = _html()
    mobile = _between(html, "@media (max-width: 900px)", "@media print")
    assert ".compare-occupations-grid {\n        grid-template-columns: 1fr;\n      }" in mobile
    assert ".compare-selection-bar {" in mobile
    assert "#open-compare-occupations-btn {" in mobile
    assert ".compare-occupation-actions .worker-outlook-button {" in mobile
    assert "min-height: 44px" in mobile


def test_compare_occupations_grid_uses_responsive_cards_on_desktop():
    html = _html()
    assert ".compare-occupations-grid {\n      display: grid;\n      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));" in html
    assert "overflow-wrap: anywhere;" in _fn(html, ".compare-occupation-title {", ".compare-occupation-code {")


# --- Existing systems remain unforked ---

def test_compare_occupations_stage_is_registered_in_worker_workspace_labels():
    html = _html()
    assert '"compare-occupations": "Compare Occupations"' in html
    assert 'stage === "saved-occupations" || stage === "next-investigation" || stage === "compare-occupations"' in html


def test_handle_worker_stage_action_loads_compare_occupations():
    html = _html()
    handler = _fn(html, "function handleWorkerStageAction(button)", "function openLaborersWorkspace(")
    assert 'load === "compare-occupations"' in handler
    assert "void loadCompareOccupations();" in handler


def test_compare_occupations_nav_link_exists_alongside_existing_stages():
    html = _html()
    assert 'data-worker-stage-target="compare-occupations">Compare Occupations</button>' in html
    assert 'data-worker-stage-target="saved-occupations"' in html
    assert 'data-worker-stage-target="investigate"' in html


# --- Safety boundary preserved (informational only) ---

def test_compare_card_actions_are_informational_only_no_application_or_contact():
    html = _html()
    skeleton_fn = _fn(html, "function compareOccupationCardSkeleton(record)", "async function loadCompareOccupationCard")
    assert "Investigate" in skeleton_fn
    assert "Find live jobs" in skeleton_fn
    assert "Remove from comparison" in skeleton_fn
    for prohibited in ("apply now", "submit application", "contact employer", "auto-apply", "autonomous"):
        assert prohibited not in skeleton_fn.lower()
