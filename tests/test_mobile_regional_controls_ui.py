from pathlib import Path


HTML = Path("web/index.html").read_text()


def test_mobile_regional_controls_are_reserved_below_outlook_panel():
    assert """
      .info-panel {
        top: auto;
        left: 14px;
        right: 14px;
        bottom: 126px;
        width: auto;
        max-height: 70vh;
        transition: max-height 180ms ease;
      }
""" in HTML

    assert """
      .layer-bar {
        left: 14px;
        right: 14px;
        bottom: 14px;
        max-width: none;
        max-height: 102px;
        overflow-y: auto;
        z-index: 11;
      }
""" in HTML


def test_mobile_labor_controls_use_their_own_row():
    assert """
      .labor-map-controls {
        flex: 1 1 100%;
        margin-left: 0;
      }
""" in HTML

    assert """
      .labor-map-controls select {
        min-width: 0;
        max-width: 100%;
      }
""" in HTML


def test_desktop_layer_bar_position_is_preserved():
    assert """
    .layer-bar {
      position: absolute;
      left: 20px;
      bottom: 58px;
""" in HTML
