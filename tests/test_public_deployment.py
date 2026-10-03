import json
from pathlib import Path

import pytest

from scripts.prepare_pages import DASHBOARD_FILES, WEB_FILES, build_site, validate_site


ROOT = Path(__file__).resolve().parents[1]


def test_pages_publishes_only_allowlisted_assets(tmp_path):
    site = build_site(tmp_path / "site")
    expected = set(WEB_FILES) | {f"dashboard/{name}" for name in DASHBOARD_FILES}
    actual = {path.relative_to(site).as_posix() for path in site.rglob("*") if path.is_file()}
    assert actual == expected
    assert "fetch.js" in actual
    assert "data/geography/ne_110m_admin_0_countries.geojson" in actual
    assert "carl-live/assets/index-Ciumrzk3.js" in actual
    assert "stex-review.html" not in actual
    assert not any(name.endswith((".bak", ".py", ".yaml", ".log")) for name in actual)


def test_pages_key_is_serialized_not_shell_interpolated(tmp_path):
    key = 'synthetic-"-test\\value'
    site = build_site(tmp_path / "site", key)
    config = (site / "api_config.js").read_text()
    assert f"window.GVAI_GOOGLE_MAPS_API_KEY = {json.dumps(key)};" in config
    workflow = (ROOT / ".github/workflows/pages.yml").read_text()
    assert "python scripts/prepare_pages.py" in workflow
    assert "cp -R web/*" not in workflow


def test_pages_rejects_unknown_existing_output(tmp_path):
    (tmp_path / "secret.txt").write_text("not public")
    with pytest.raises(ValueError, match="empty directory"):
        build_site(tmp_path)


def test_pages_checks_missing_local_assets(tmp_path):
    site = build_site(tmp_path / "site")
    (site / "fetch.js").unlink()
    with pytest.raises(ValueError, match="Missing public asset"):
        validate_site(site)


def test_railway_has_one_authoritative_startup_and_build_install():
    config = json.loads((ROOT / "railway.json").read_text())
    assert config["build"]["buildCommand"] == "python -m pip install -r requirements.txt"
    assert config["deploy"]["startCommand"] == "privacy/start_railway.sh"
    assert config["deploy"]["healthcheckPath"] == "/api/health"
    assert (ROOT / "Procfile").read_text().strip() == "web: privacy/start_railway.sh"
    launcher = (ROOT / "privacy/start_railway.sh").read_text()
    assert "python -m gunicorn" in launcher
    assert "--workers" in launcher and "--timeout" in launcher
    assert "gvai.api_service:app" in launcher
    assert "pip install" not in launcher
    assert "GVAI_PRIVATE_BUILD_MODE" in launcher


def test_normal_pr_ci_runs_primary_product_suite():
    workflow = (ROOT / ".github/workflows/product-ci.yml").read_text()
    assert "pull_request:" in workflow
    assert "python -m pytest tests -q" in workflow
    assert "node --test tests/frontend/*.test.cjs" in workflow
    assert "--ignore" not in workflow