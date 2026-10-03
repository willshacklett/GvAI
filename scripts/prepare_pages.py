import argparse
import json
import os
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB_FILES = (
    "index.html", "api_config.js", "fetch.js", "gv-carl-logo.svg", "gv-logo.png",
    "favicon.ico", "favicon.png", "style.css", "dashboard.js", "gvai-voice.js",
    "manifest.json", "service-worker.js", "CNAME", "robots.txt", "sitemap.xml",
    "data/geography/ne_110m_admin_0_countries.geojson",
    "carl-live/index.html", "carl-live/assets/index-Ciumrzk3.js",
    "change-impact/index.html",
)
DASHBOARD_FILES = (
    "index.html", "style.css", "dashboard.js", "conversation_gv_demo.json",
    "gvai_state.json", "data/sentinel_output.json",
    "gv-kernel-observatory/index.html", "gv-kernel-observatory/observatory.js",
    "gv-kernel-observatory/style.css", "gv_reports/index.html",
    "gv_reports/alpha_phase_report.html", "gv_reports/gv_hypnotic_signal.html",
    "gv_reports/regime_stability_report.html", "gv_reports/research_summary.html",
    "gv_reports/sample_service_latency_report.html", "gv_reports/transition_review.html",
    "gv_reports/universal_scalar.html", "gv_reports/war_room.html",
)


class AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "img", "iframe", "source"} and attributes.get("src"):
            self.references.append(attributes["src"])
        if tag in {"link", "a"} and attributes.get("href"):
            self.references.append(attributes["href"])


def validate_site(destination):
    for html in destination.rglob("*.html"):
        parser = AssetReferences()
        parser.feed(html.read_text())
        for reference in parser.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = unquote(parsed.path)
            target = destination / path.lstrip("/") if path.startswith("/") else html.parent / path
            target = target.resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError(f"Public reference escapes site: {html.name}: {reference}")
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                raise ValueError(f"Missing public asset: {html.name}: {reference}")
    manifest = json.loads((destination / "manifest.json").read_text())
    for icon in manifest.get("icons", []):
        if not (destination / icon["src"]).is_file():
            raise ValueError("Missing manifest icon")


def build_site(destination, google_maps_key=""):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Pages output must be an empty directory.")
    for folder, files, prefix in (("web", WEB_FILES, ""), ("dashboard", DASHBOARD_FILES, "dashboard")):
        for name in files:
            source = ROOT / folder / name
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Missing or unsafe allowlisted asset: {folder}/{name}")
            target = destination / prefix / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    if google_maps_key:
        with (destination / "api_config.js").open("a") as config:
            config.write("\nwindow.GVAI_GOOGLE_MAPS_API_KEY = " + json.dumps(google_maps_key) + ";\n")
    validate_site(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("_site"))
    args = parser.parse_args()
    build_site(args.output, os.getenv("GVAI_GOOGLE_MAPS_API_KEY", ""))