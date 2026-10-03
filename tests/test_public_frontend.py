from pathlib import Path
from html.parser import HTMLParser


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web/index.html").read_text()


def test_regional_failure_and_retry_preserve_selection_guard():
    assert 'id="regional-error"' in HTML
    assert "Regional data temporarily unavailable. Retry or select another region." in HTML
    assert 'id="regional-retry"' in HTML
    assert 'const fetch = window.GVAI.fetchJSON;' in HTML
    catch = HTML[HTML.index('"Regional intelligence lookup failed"'):HTML.index("function flyToProfile")]
    assert "if (requestId !== activeRegionRequestId) return;" in catch
    assert "showRegionalFailure(requestId)" in catch
    assert 'element.textContent = "Unavailable"' in HTML
    assert 'typeof data.supported !== "boolean"' in HTML


def test_workspace_width_is_bounded_and_content_responsive():
    assert "width: min(64vw, 960px);" in HTML
    assert "left: 430px" not in HTML
    assert "right: 430px" not in HTML
    assert "@container (max-width: 760px)" in HTML
    assert "container-type: inline-size;" in HTML
    assert "overflow-x: hidden;" in HTML
    assert "#app.workspace-open .info-panel" in HTML
    assert 'id="workspace-switcher"' in HTML
    assert "updateWorkspaceLayout()" in HTML
    for audience in ("laborers", "business", "government"):
        assert f'id="{audience}-workspace"' in HTML
    assert "new Cesium.Viewer" in HTML


def test_metadata_and_semantic_landmarks():
    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    parser = Tags()
    parser.feed(HTML)
    assert sum(tag == "main" for tag, attrs in parser.tags) == 1
    assert sum(tag == "h1" for tag, attrs in parser.tags) == 1
    assert any(tag == "header" for tag, attrs in parser.tags)
    assert any(tag == "nav" for tag, attrs in parser.tags)
    assert 'name="description"' in HTML
    assert 'property="og:title"' in HTML
    assert 'property="og:description"' in HTML
    assert 'rel="canonical" href="https://gvai.io/"' in HTML
    for action in ("zoom-in", "zoom-out", "reset"):
        assert f'id="globe-{action}"' in HTML