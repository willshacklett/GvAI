from pathlib import Path


HTML = Path("web/index.html").read_text()


def test_browser_tab_uses_canonical_gv_svg():
    assert (
        '<link rel="icon" type="image/svg+xml" '
        'href="/gv-carl-logo.svg?v=4" />'
    ) in HTML

    assert (
        '<link rel="shortcut icon" type="image/svg+xml" '
        'href="/gv-carl-logo.svg?v=4" />'
    ) in HTML


def test_browser_tab_does_not_prefer_legacy_favicon():
    head = HTML.split("</head>", 1)[0]
    assert 'href="/favicon.ico' not in head
    assert 'href="/favicon.png' not in head
