from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _government_slice():
    html = _html()
    start = html.index('id="government-workspace"')
    end = html.index('<div class="layer-bar">', start)
    return html[start:end]


def test_government_workspace_entry_exists():
    html = _html()
    assert 'id="open-government-workspace-btn"' in html
    assert 'id="government-workspace" class="business-workspace government-workspace"' in html
    assert "Government Regional Intelligence" in html
    assert "Open Government workspace" in html
    assert "Open Business workspace" in html
    assert "Open Laborers workspace" in html


def test_government_workflow_is_region_evidence_first():
    government = _government_slice()
    for text in (
        "1. Choose region",
        "2. Review regional conditions",
        "3. Inspect structural exposure",
        "4. Review evidence boundaries",
        "What does labor availability show?",
        "What does workforce mix show?",
        "What does housing pressure show?",
        "What does regional STEX show?",
        "What evidence is missing or less specific?",
    ):
        assert text in government


def test_government_preserves_stex_semantics():
    government = _government_slice()
    assert "structural task exposure" in government
    assert "not percent automatable" in government
    assert "not a probability that an occupation disappears" in government
    assert "not as a prediction" in government


def test_government_preserves_missing_evidence():
    government = _government_slice()
    assert "Missing evidence remains unavailable" in government
    assert "replaced with zero" in government
    assert "Unsupported, unavailable, or broader-category evidence" in government


def test_government_safety_systems_is_boundary_only():
    government = _government_slice()
    assert "GVAI Safety Systems boundary" in government
    assert "separate implementation" in government
    assert "does not copy or silently activate" in government
    assert "does not claim active governance" in government


def test_government_workspace_open_close_behavior_exists():
    html = _html()
    assert "function syncGovernmentRegionContext()" in html
    assert "function openGovernmentWorkspace()" in html
    assert "function closeGovernmentWorkspace()" in html
    assert 'document.getElementById("open-government-workspace-btn").addEventListener("click", openGovernmentWorkspace);' in html
    assert 'document.getElementById("close-government-workspace-btn").addEventListener("click", closeGovernmentWorkspace);' in html
    assert "closeGovernmentWorkspace();" in html
    assert "closeBusinessWorkspace();" in html

    start = html.index('function openLaborersWorkspace')
    end = html.index('function closeLaborersWorkspace', start)
    laborers_open = html[start:end]
    assert "closeGovernmentWorkspace();" in laborers_open


def test_government_uses_existing_responsive_workspace_layout():
    html = _html()
    government = _government_slice()
    assert 'class="business-workspace government-workspace"' in government
    mobile = html[html.index("@media (max-width: 900px)"):html.index("@media print")]
    assert ".business-workspace" in mobile
    assert ".business-workflow" in mobile
    assert ".business-evidence-grid" in mobile


def test_government_workspace_has_no_scores_rankings_or_policy_verdicts():
    government = _government_slice().lower()

    prohibited = (
        "government score:",
        "best jurisdiction",
        "worst jurisdiction",
        "policy score:",
        "recommended policy:",
        "policy verdict:",
    )

    for text in prohibited:
        assert text not in government

    assert "does not combine these signals into a government score" in government
    assert "does not convert them into a government score" in government
    assert "rank jurisdictions" in government
    assert "does not" in government
    assert "policy recommendation" in government
