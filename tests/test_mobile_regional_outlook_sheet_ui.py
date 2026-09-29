from pathlib import Path


HTML = Path("web/index.html").read_text()


def test_mobile_regional_outlook_has_accessible_toggle():
    assert 'id="regional-outlook-panel"' in HTML
    assert 'id="regional-outlook-toggle"' in HTML
    assert 'aria-expanded="true"' in HTML
    assert 'aria-controls="regional-outlook-content"' in HTML
    assert 'id="regional-outlook-content"' in HTML


def test_mobile_regional_outlook_can_collapse_content():
    assert ".info-panel.is-collapsed {" in HTML
    assert ".info-panel.is-collapsed .regional-outlook-content {" in HTML
    assert "display: none;" in HTML
    assert 'classList.toggle(' in HTML
    assert '"is-collapsed",' in HTML
    assert '"aria-expanded",' in HTML


def test_collapsed_outlook_keeps_selected_region_summary():
    assert 'id="regional-outlook-summary"' in HTML
    assert 'document.getElementById(\n    "regional-outlook-summary"\n  ).textContent = profile.title;' in HTML


def test_mobile_outlook_clears_bottom_map_controls():
    assert """      .info-panel {
        top: auto;
        left: 14px;
        right: 14px;
        bottom: 126px;
        width: auto;
        max-height: 70vh;
        transition: max-height 180ms ease;
      }
""" in HTML


def test_desktop_outlook_toggle_remains_hidden():
    assert """    .regional-outlook-toggle {
      display: none;
    }
""" in HTML
