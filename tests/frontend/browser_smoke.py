import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gvai.postlabor.regional_intelligence import build_regional_intelligence


def check_site(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
        page.set_default_timeout(90000)
        errors = []
        api_mode = {"failed": True}
        chat_contexts = []
        regional_requests = []
        fixture = build_regional_intelligence({
            "supported": True, "data_available": True, "state": "Tennessee", "county": "Rutherford County",
            "state_fips": "47", "county_fips": "149", "latitude": 35.85, "longitude": -86.4,
            "acs_year": 2024, "population": 363000, "labor_force": 200000, "unemployed": 8000,
            "unemployment_rate": 4, "median_household_income": 80000, "median_home_value": 400000,
            "home_value_to_income_ratio": 5, "median_age": 36,
            "occupation_profile": {"data_available": True, "acs_year": 2024, "civilian_employed_16_plus": 192000,
                "groups": [{"group_id": "management_business_science_arts", "label": "Management, business, science, and arts", "employed": 96000, "share_percent": 50},
                           {"group_id": "service", "label": "Service occupations", "employed": 48000, "share_percent": 25},
                           {"group_id": "sales_office", "label": "Sales and office", "employed": 48000, "share_percent": 25}]},
        })
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api_route(route):
            if "/api/region/intelligence" in route.request.url:
                regional_requests.append(route.request.url)
                if api_mode["failed"]:
                    route.fulfill(status=503, json={"ok": False, "reason": "Synthetic unavailable fixture"})
                else:
                    route.fulfill(json={"ok": True, "intelligence": fixture})
            elif "/api/chat" in route.request.url:
                chat_contexts.append(route.request.post_data_json["region_context"])
                route.fulfill(json={"ok": True, "reply": "Synthetic model interpretation: observed ACS evidence is distinct from derived signals. STEX is unavailable in this fixture."})
            elif "/api/geocode" in route.request.url:
                route.fulfill(json={
                    "ok": True, "label": "Rutherford County, Tennessee",
                    "latitude": 35.85, "longitude": -86.4,
                    "country": "United States", "country_code": "us",
                    "state": "Tennessee", "county": "Rutherford County",
                })
            else:
                route.fulfill(status=503, json={"ok": False, "reason": "Synthetic unavailable fixture"})

        page.route("**/api/**", api_route)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cesium-widget canvas", timeout=60000)
        page.locator("#location-search").fill("Rutherford County")
        page.locator("#search-btn").click()
        page.wait_for_selector("#regional-error:not([hidden])", timeout=60000)
        assert page.locator("#population").text_content() == "Unavailable"
        assert "Regional data temporarily unavailable" in page.locator("#regional-shared-brief").inner_text()
        assert page.locator("#regional-retry").is_visible()
        page.locator("#regional-retry").click()
        page.wait_for_selector("#regional-error:not([hidden])", timeout=60000)
        print("Regional failure and retry verified")
        api_mode["failed"] = False
        page.locator("#regional-retry").click()
        page.wait_for_selector("#regional-shared-brief .regional-region-title", timeout=60000)
        assert page.locator("#regional-shared-brief").inner_text().find("363,000") >= 0
        assert page.locator('#regional-shared-brief [data-regional-metric="stex_coverage"]').inner_text().find("Unavailable") >= 0

        output = Path("test-results")
        output.mkdir(exist_ok=True)
        for width, height in [(1440, 900), (1366, 768), (1024, 768), (768, 1024), (390, 844)]:
            page.set_viewport_size({"width": width, "height": height})
            assert page.locator("#regional-outlook-panel").is_visible()
            if not page.locator("#audience-laborers-btn").is_visible():
                page.locator("#regional-outlook-toggle").click()
            assert page.locator("#regional-outlook-panel").evaluate("element => element.scrollWidth <= element.clientWidth + 1")
            page.locator("#audience-laborers-btn").click()
            for audience in ["laborers", "business", "government"]:
                page.locator(f"#switch-{audience}").click()
                panel = page.locator(f"#{audience}-workspace")
                assert panel.is_visible()
                assert not page.locator("#regional-outlook-panel").is_visible()
                assert page.locator("#laborers-workspace:visible, #business-workspace:visible, #government-workspace:visible").count() == 1
                measurements = panel.evaluate("""element => ({
                    width: element.clientWidth, scroll: element.scrollWidth,
                    right: element.getBoundingClientRect().right
                })""")
                assert measurements["scroll"] <= measurements["width"] + 1, measurements
                assert measurements["right"] <= width, measurements
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                shell = panel.locator(".laborers-workspace-shell, .business-workspace-shell")
                assert shell.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
                brief = panel.locator("[data-regional-brief]")
                brief.scroll_into_view_if_needed()
                assert brief.locator(".regional-region-title").inner_text() == "Rutherford County, Tennessee"
                assert panel.locator("[data-region-label]").inner_text() == "Rutherford County, Tennessee"
                assert "Partial evidence" in brief.inner_text()
                attribution = brief.locator(".regional-source-note summary").first
                attribution.scroll_into_view_if_needed()
                assert attribution.is_visible()
                assert "Source data" in attribution.inner_text()
                attribution.click()
                assert "ACS B01003_001E" in brief.inner_text()
                interpretation = brief.locator(f'[data-audience-section="{audience}"]')
                interpretation.scroll_into_view_if_needed()
                assert interpretation.is_visible()
                page.locator("#ask-btn").click()
                page.locator("#regional-ask-form button").click()
                page.wait_for_function("document.getElementById('regional-ask-reply').textContent.includes('Synthetic model interpretation')")
                assert chat_contexts[-1]["audience"] == audience
                assert chat_contexts[-1]["region"]["id"] == "US:county:47149"
                assert chat_contexts[-1]["sources"]["acs"]["vintage"] == 2024
                page.locator("#simulate-btn").click()
                for name, value in (("workers", "10"), ("hours", "40"), ("share", "20"), ("saving", "50")):
                    page.locator(f"#scenario-{name}").fill(value)
                page.locator("#regional-scenario-form button").click()
                assert "40 task hours/week could be released" in page.locator("#regional-scenario-result").inner_text()
                assert "Not observed regional hours or predicted jobs removed" in page.locator("#regional-scenario-result").inner_text()
                page.locator("#regional-ask-pane").evaluate("element => element.open = false")
                page.locator("#regional-scenario-pane").evaluate("element => element.open = false")
                shell.evaluate("element => element.scrollTop = 0")
                close = panel.locator(".laborers-workspace-close")
                assert close.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                assert page.locator(f"#switch-{audience}").get_attribute("aria-selected") == "true"
                tab = page.locator(f"#switch-{audience}")
                assert tab.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                search = page.locator("#location-search")
                assert search.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                page.screenshot(path=str(output / f"{audience}-{width}.png"))
                print(width, audience, json.dumps(measurements))
            page.locator("#close-government-workspace-btn").click()
            assert page.locator("#laborers-workspace:visible, #business-workspace:visible, #government-workspace:visible").count() == 0
            assert page.locator("#regional-outlook-panel").is_visible()
            page.screenshot(path=str(output / f"globe-{width}.png"))
            pixels = page.evaluate("""() => new Promise(resolve => {
                requestAnimationFrame(() => {
                    const canvas = document.querySelector('.cesium-widget canvas');
                    const context = canvas.getContext('webgl2') || canvas.getContext('webgl');
                    const data = new Uint8Array(canvas.width * canvas.height * 4);
                    context.readPixels(0, 0, canvas.width, canvas.height, context.RGBA, context.UNSIGNED_BYTE, data);
                    let colored = 0;
                    for (let offset = 0; offset < data.length; offset += 4) {
                        if (data[offset] + data[offset + 1] + data[offset + 2] > 30) colored++;
                    }
                    resolve(colored);
                });
            })""")
            assert pixels > 1000, f"Blank globe canvas at {width}: {pixels} colored pixels"
            page.locator("#globe-zoom-in").click()
            page.locator("#globe-zoom-out").click()
            print(width, "globe colored pixels", pixels)
        assert not any("/api/region/labor-intelligence" in url or "/api/stex/regional" in url for url in regional_requests)
        print("Structured Ask and labelled scenarios verified for all 15 audience/viewport combinations")
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8090")
    check_site(parser.parse_args().url)