from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _html():
    return (ROOT / "web/index.html").read_text()


def _hub():
    html = _html()
    start = html.index('<section class="audience-hub"')
    end = html.index('<section class="worker-journey"', start)
    return html[start:end]


def test_audience_hub_presents_three_product_paths():
    hub = _hub()
    assert "Choose your path" in hub
    assert "One regional intelligence platform. Three ways in." in hub
    assert 'data-audience="laborers"' in hub
    assert 'data-audience="business"' in hub
    assert 'data-audience="government"' in hub


def test_audience_hub_uses_plain_language_jobs_to_be_done():
    hub = _hub()
    assert "Understand your work and options" in hub
    assert "Understand workforce conditions" in hub
    assert "Understand regional labor conditions" in hub
    assert "The globe remains the shared regional evidence surface" in hub


def test_audience_hub_buttons_are_wired_to_existing_workspaces():
    html = _html()
    assert 'id="audience-laborers-btn"' in html
    assert 'id="audience-business-btn"' in html
    assert 'id="audience-government-btn"' in html
    assert 'document.getElementById("audience-laborers-btn").addEventListener("click", () => openLaborersWorkspace());' in html
    assert 'document.getElementById("audience-business-btn").addEventListener("click", openBusinessWorkspace);' in html
    assert 'document.getElementById("audience-government-btn").addEventListener("click", openGovernmentWorkspace);' in html


def test_existing_entry_points_remain_available():
    html = _html()
    assert 'id="open-laborers-workspace-btn"' in html
    assert 'id="open-business-workspace-btn"' in html
    assert 'id="open-government-workspace-btn"' in html
    assert 'id="start-worker-profile-btn"' in html


def test_audience_hub_stacks_on_mobile():
    html = _html()
    mobile = html[html.index("@media (max-width: 900px)"):html.index("@media print")]
    assert ".audience-hub-grid" in mobile
    assert "grid-template-columns: 1fr;" in mobile


def test_audience_hub_does_not_create_composite_score_or_verdict():
    hub = _hub().lower()
    for prohibited in (
        "gvai score",
        "laborer score",
        "business score",
        "government score",
        "best path",
        "recommended path",
        "ranking",
        "winner",
    ):
        assert prohibited not in hub
