from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_selected_state_drives_nationwide_acs_overlays():
    html = (ROOT / "web/index.html").read_text()

    assert (
        "/api/region/labor-availability?"
        "state=${encodeURIComponent(stateFips)}"
        in html
    )
    assert (
        "/api/region/workforce-mix?"
        "state=${encodeURIComponent(stateFips)}"
        in html
    )
    assert (
        "/api/region/housing-pressure?"
        "state=${encodeURIComponent(stateFips)}"
        in html
    )

    assert (
        "`STATE='${normalizedStateFips}'`"
        in html
    )

    assert (
        "loadTennesseeCountyBoundaries(\n"
        "        selectedStateFips\n"
        "      )"
        in html
    )


def test_stex_remains_explicitly_tennessee_only():
    html = (ROOT / "web/index.html").read_text()

    assert (
        "/api/region/stex-coverage?"
        "state=47&year=2025"
        in html
    )

    assert (
        'if (normalizedStateFips === "47")'
        in html
    )

    assert "loadTennesseeSTEXCoverageOverlay" in html


def test_switching_states_clears_old_overlay_data():
    html = (ROOT / "web/index.html").read_text()

    assert "activeCountyOverlayStateFips" in html
    assert "clearCountyOverlayDataSources" in html

    assert (
        "activeCountyOverlayStateFips !==\n"
        "      normalizedStateFips"
        in html
    )
