from pathlib import Path


HTML = Path("web/index.html").read_text()


def test_mobile_outlook_handle_supports_pointer_drag():
    assert '"pointerdown"' in HTML
    assert '"pointermove"' in HTML
    assert '"pointerup"' in HTML
    assert "setPointerCapture(" in HTML
    assert "releasePointerCapture(" in HTML


def test_mobile_outlook_drag_has_directional_snap():
    assert "REGIONAL_OUTLOOK_DRAG_THRESHOLD = 36" in HTML
    assert "setRegionalOutlookCollapsed(deltaY > 0);" in HTML


def test_drag_does_not_also_trigger_click_toggle():
    assert "regionalOutlookDragged = true;" in HTML
    assert """if (regionalOutlookDragged) {
      regionalOutlookDragged = false;
      return;
    }""" in HTML


def test_mobile_outlook_handle_owns_touch_gesture():
    assert "touch-action: none;" in HTML
    assert "user-select: none;" in HTML
