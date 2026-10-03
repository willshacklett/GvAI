import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def check_site(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
        page.set_default_timeout(90000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def api_route(route):
            if "/api/geocode" in route.request.url:
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
        assert page.locator("#population").inner_text() == "Unavailable"
        assert page.locator("#regional-retry").is_visible()
        page.locator("#regional-retry").click()
        page.wait_for_selector("#regional-error:not([hidden])", timeout=60000)
        print("Regional failure and retry verified")

        output = Path("test-results")
        output.mkdir(exist_ok=True)
        for width, height in [(1366, 768), (1024, 768), (390, 844)]:
            page.set_viewport_size({"width": width, "height": height})
            for audience in ["laborers", "business", "government"]:
                page.evaluate(f"document.getElementById('audience-{audience}-btn').click()")
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
                shell = panel.locator(".laborers-workspace-shell, .business-workspace-shell")
                assert shell.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
                close = panel.locator(".laborers-workspace-close")
                assert close.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                assert page.locator(f"#switch-{audience}").get_attribute("aria-selected") == "true"
                tab = page.locator(f"#switch-{audience}")
                assert tab.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                search = page.locator("#location-search")
                assert search.evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 5, element.getBoundingClientRect().y + 5))")
                page.screenshot(path=str(output / f"{audience}-{width}.png"))
                print(width, audience, json.dumps(measurements))
            page.evaluate("document.getElementById('close-government-workspace-btn').click()")
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
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8090")
    check_site(parser.parse_args().url)