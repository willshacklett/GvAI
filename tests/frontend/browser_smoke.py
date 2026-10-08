import argparse
import copy
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gvai.postlabor.regional_intelligence import build_regional_intelligence
from gvai.decision_intelligence import assess


def check_site(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1366, "height": 768}, ignore_https_errors=True)
        page.set_default_timeout(90000)
        errors = []
        api_mode = {"failed": True, "hold_chat": False, "hold_business": False, "hold_occupation": False, "actions": []}
        pending = {"chat": [], "business": [], "occupation": []}
        chat_contexts = []
        investigations = []
        regional_requests = []
        def selected_fixture(identity):
            selected = copy.deepcopy(fixture)
            if identity == "US:county:47065":
                selected["region"].update(id=identity, label="Hamilton County, Tennessee",
                    county="Hamilton County", county_fips="065", latitude=35.2, longitude=-85.2)
                selected["metrics"]["labor_force"]["value"] = 100000
                selected["metrics"]["median_home_value"]["value"] = 240000
                selected["metrics"]["home_value_to_income_ratio"]["value"] = 3
            return selected
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
        page.add_init_script("""localStorage.setItem('gvai.workerProfile.v1', JSON.stringify({
            profile_version: 'v1', current_occupation: {occupation_code: '37-2021.00', occupation_title: 'Pest Control Workers'},
            experience: {}, education: {}, credentials: [], skills: [], wage: {}, mobility: {},
            preferences: {notes: 'PRIVATE_PROFILE_SENTINEL'}
        }));""")
        def occupation(code):
            return {"occupation_code": code, "occupation_title": "Pest Control Workers" if code == "37-2021.00" else "Software Developers",
                    "structural_exposure": 25 if code == "37-2021.00" else 55, "rated_task_count": 1,
                    "rubric_version": "Synthetic STEX fixture", "source": {"name": "O*NET fixture", "tasks_year": 2026}}

        business_fixture = {"ok": True, "supported": True, "occupation": occupation("37-2021.00"),
            "region": {"county": "Rutherford County", "oews_area_code": "0034980"},
            "occupation_evidence": {"employment": {"employment": 1000, "source_year": 2025, "source": "BLS OEWS fixture"},
                "wage": {"median_hourly_wage": 25, "median_annual_wage": 52000, "source_year": 2025, "source": "BLS OEWS fixture"}}}

        def api_route(route):
            if "/api/region/intelligence" in route.request.url:
                regional_requests.append(route.request.url)
                if api_mode["failed"]:
                    route.fulfill(status=503, json={"ok": False, "reason": "Synthetic unavailable fixture"})
                else:
                    identity = "US:county:47065" if parse_qs(urlsplit(route.request.url).query).get("lat") == ["35.2"] else "US:county:47149"
                    selected = selected_fixture(identity)
                    route.fulfill(json={"ok": True, "intelligence": selected})
            elif "/api/chat" in route.request.url:
                chat_contexts.append(route.request.post_data_json.get("region_context"))
                investigations.append(route.request.post_data_json.get("intelligence_session"))
                if api_mode["hold_chat"]:
                    pending["chat"].append(route)
                    return
                context = route.request.post_data_json.get("intelligence_session", {})
                read = assess(context.get("investigation"), [selected_fixture(item["id"]) for item in context.get("regions", [])],
                              context.get("comparison_ids", []))
                route.fulfill(json={"ok": True, "reply": "Synthetic model interpretation: observed ACS evidence is distinct from derived signals. STEX is unavailable in this fixture.",
                    "action_protocol": "gvai.ui-actions.v1", "actions": api_mode["actions"], "decision_read": read})
            elif "/api/geocode" in route.request.url:
                if parse_qs(urlsplit(route.request.url).query).get("q") == ["Springfield"]:
                    route.fulfill(json={"ok": True, "requires_choice": True, "candidates": [
                        {"label": "Springfield, Tennessee · synthetic choice", "latitude": 35.85, "longitude": -86.4,
                         "country_code": "us", "state": "Tennessee", "county": "Rutherford County"},
                        {"label": "Springfield, Missouri · synthetic choice", "latitude": 37.2, "longitude": -93.3,
                         "country_code": "us", "state": "Missouri", "county": "Greene County"}]})
                    return
                if parse_qs(urlsplit(route.request.url).query).get("q") == ["Hamilton County, Tennessee"]:
                    route.fulfill(json={"ok": True, "label": "Hamilton County, Tennessee", "latitude": 35.2,
                        "longitude": -85.2, "country": "United States", "country_code": "us",
                        "state": "Tennessee", "county": "Hamilton County"})
                    return
                if parse_qs(urlsplit(route.request.url).query).get("q") == ["France"]:
                    route.fulfill(json={"ok": True, "label": "France", "latitude": 46.2, "longitude": 2.2, "country": "France", "country_code": "fr"})
                    return
                route.fulfill(json={
                    "ok": True, "label": "Rutherford County, Tennessee",
                    "latitude": 35.85, "longitude": -86.4,
                    "country": "United States", "country_code": "us",
                    "state": "Tennessee", "county": "Rutherford County",
                })
            elif "/api/stex/occupations" in route.request.url:
                route.fulfill(json={"ok": True, "profiles": [occupation("15-1252.00"), occupation("37-2021.00")]})
            elif "/api/stex/occupation?" in route.request.url:
                code = parse_qs(urlsplit(route.request.url).query)["code"][0]
                if api_mode["hold_occupation"] and code == "15-1252.00":
                    pending["occupation"].append(route)
                    page.evaluate("window.__heldOccupation = true")
                    return
                route.fulfill(json={"ok": True, "profile": occupation(code)})
            elif "/api/stex/tasks?" in route.request.url:
                route.fulfill(json={"ok": True, "contributors": [{"task_id": "fixture", "task_title": "Inspect worksite", "source_importance": 100,
                    "structural_exposure": 25, "augmentation_likelihood": 30, "stex_contribution_points": 25,
                    "importance_status": "rated", "rationale": "Synthetic audit rationale; not a guarantee."}]})
            elif "/api/business/workforce-intelligence" in route.request.url:
                if api_mode["hold_business"]:
                    pending["business"].append(route)
                    return
                route.fulfill(json=business_fixture)
            elif "/api/worker/live-jobs/capabilities" in route.request.url:
                country = parse_qs(urlsplit(route.request.url).query).get("country", ["US"])[0]
                route.fulfill(json={"ok": True, "state": "available" if country == "US" else "unsupported",
                    "providers": [{"state": "configured", "supported_search_filters": ["location"], "search_filter_options": {}}]})
            elif "/api/worker/live-jobs?" in route.request.url:
                route.fulfill(json={"ok": True, "status": "available_with_results", "provider": "Synthetic provider",
                    "search_context": {"location": "Austin, Texas", "country_code": "US"}, "openings": [{"title": "Synthetic opening",
                    "source_attribution": "Synthetic provider", "provider": "Synthetic provider", "apply_url": "https://example.org/job"}]})
            else:
                route.fulfill(status=503, json={"ok": False, "reason": "Synthetic unavailable fixture"})

        page.route("**/api/**", api_route)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cesium-widget canvas", timeout=60000)
        # Keep software-rendered globe smoke bounded without changing DOM viewports.
        page.evaluate("""() => {
            window.gvaiViewer.resolutionScale = 0.5;
            window.gvaiViewer.targetFrameRate = 12;
            window.gvaiViewer.scene.requestRenderMode = true;
            window.gvaiViewer.scene.maximumRenderTimeChange = Infinity;
        }""")
        output = Path("test-results")
        output.mkdir(exist_ok=True)
        for width, height in [(1440, 900), (390, 844)]:
            page.set_viewport_size({"width": width, "height": height})
            assert page.locator("#intelligence-guide > summary").inner_text() == "What are you trying to understand?"
            assert page.locator("#regional-question").get_attribute("placeholder") == "Ask GVAI about work, hiring, regions, careers, or expansion..."
            assert page.locator("#regional-question").input_value() == ""
            assert page.locator(".brand-sub").inner_text() == "Intelligence for work, workforce, and place"
            assert page.locator("#intelligence-starters button").all_text_contents() == [
                "Find better work", "Find where to hire", "Compare places", "Understand my region"]
            for selector in ["#regional-outlook-panel", "#intelligence-investigation", "#intelligence-comparison",
                             "#intelligence-why", "#intelligence-audience-control", ".layer-bar", ".legend", "#location-search"]:
                assert not page.locator(selector).is_visible(), selector
            assert page.locator("#laborers-workspace:visible, #business-workspace:visible, #government-workspace:visible").count() == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("#regional-question").evaluate("element => element.contains(document.elementFromPoint(element.getBoundingClientRect().x + 10, element.getBoundingClientRect().y + 10))")
            assert page.evaluate("document.querySelector('.cesium-widget-credits').getBoundingClientRect().bottom <= document.getElementById('intelligence-guide').getBoundingClientRect().top")
            pixels = page.evaluate("""() => {
                window.gvaiViewer.scene.requestRender();
                window.gvaiViewer.render();
                const canvas = document.querySelector('.cesium-widget canvas');
                const context = canvas.getContext('webgl2') || canvas.getContext('webgl');
                const data = new Uint8Array(canvas.width * canvas.height * 4);
                context.readPixels(0, 0, canvas.width, canvas.height, context.RGBA, context.UNSIGNED_BYTE, data);
                let colored = 0;
                for (let offset = 0; offset < data.length; offset += 4) {
                    if (data[offset] + data[offset + 1] + data[offset + 2] > 30) colored++;
                }
                return colored;
            }""")
            assert pixels > 1000, f"Blank initial globe at {width}: {pixels}"
            page.screenshot(path=str(output / f"homepage-{width}.png"))
        page.set_viewport_size({"width": 1366, "height": 768})
        for index, audience in enumerate(["laborers", "business", "business", "government"]):
            page.locator("#intelligence-starters button").nth(index).click()
            page.wait_for_function("!document.querySelector('#regional-ask-form button').disabled")
            assert investigations[-1]["audience"] == audience
            assert investigations[-1]["selected_region_id"] is None
            assert page.locator("#laborers-workspace:visible, #business-workspace:visible, #government-workspace:visible").count() == 0
            if index == 2:
                assert page.locator("#intelligence-comparison").is_visible()
            page.locator("#intelligence-clear").click()
        print("Uncluttered desktop/mobile homepage and four starter audience routes verified", flush=True)
        assert page.locator("#intelligence-starters").is_visible()
        api_mode["actions"] = [{"type": "set_audience", "audience": "business"}]
        page.locator('[data-intelligence-prompt][data-audience="business"]').first.click()
        page.wait_for_function("document.getElementById('intelligence-action-status').textContent.includes('completed')")
        assert investigations[-1]["audience"] == "business"
        assert investigations[-1]["selected_region_id"] is None
        assert chat_contexts[-1] is None
        api_mode["actions"] = []
        page.locator("#intelligence-guide").evaluate("element => element.open = false")
        page.locator("#close-business-workspace-btn").click()
        page.locator("#exploration-tools > summary").click()
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
        for width, height in [(1440, 900), (390, 844)]:
            print("Starting intelligence journey", width, flush=True)
            page.set_viewport_size({"width": width, "height": height})
            page.locator("#intelligence-guide").evaluate("element => element.open = true")
            page.locator("#regional-ask-pane").evaluate("element => element.open = true")
            page.locator("#intelligence-comparison").evaluate("element => element.open = true")
            page.locator("#intelligence-add-region").click()
            camera_before = page.evaluate("window.gvaiViewer.camera.positionCartographic.longitude")
            api_mode["actions"] = [{"type": "select_region", "query": "Hamilton County, Tennessee"},
                {"type": "set_audience", "audience": "government"}, {"type": "open_region_evidence"},
                {"type": "eval", "code": "window.INJECTION_SENTINEL = true"}]
            page.locator("#regional-question").fill("Take me to Hamilton County, Tennessee.")
            page.locator("#regional-ask-form button").click()
            print("Navigation conversation submitted", width, flush=True)
            page.wait_for_function("document.getElementById('intelligence-action-status').textContent.includes('rejected')")
            page.wait_for_function("document.getElementById('intelligence-context').textContent.includes('Hamilton County')")
            assert page.locator("#government-workspace").is_visible()
            print("AI selection and audience completed", width, flush=True)
            page.wait_for_function("Math.abs(window.gvaiViewer.camera.positionCartographic.longitude - (-85.2 * Math.PI / 180)) < .01")
            assert page.evaluate("window.gvaiViewer.camera.positionCartographic.longitude") != camera_before
            assert page.evaluate("window.INJECTION_SENTINEL") is None
            assert "Unavailable" in page.locator("#intelligence-why-content").inner_text()
            page.locator("#intelligence-add-region").click()
            api_mode["actions"] = [{"type": "compare_regions", **(
                {"queries": ["Rutherford County, Tennessee", "Hamilton County, Tennessee"]} if width == 390
                else {"region_ids": ["US:county:47149", "US:county:47065"]})}]
            page.locator("#regional-question").fill("Compare it with the first one. What about housing?")
            page.locator("#regional-ask-form button").click()
            print("Comparison conversation submitted", width, flush=True)
            page.wait_for_function("document.getElementById('intelligence-action-status').textContent.includes('compare regions: completed')")
            assert investigations[-1]["audience"] == "government"
            assert investigations[-1]["comparison_ids"] == ["US:county:47149", "US:county:47065"]
            assert any("Take me to Hamilton" in message["content"] for message in investigations[-1]["messages"])
            assert "PRIVATE_PROFILE_SENTINEL" not in json.dumps(investigations[-1])
            assert page.locator("#intelligence-comparison-content table").count() == 1
            page.screenshot(path=str(output / f"intelligence-{width}.png"))
            api_mode["actions"] = []
            page.locator("#intelligence-guide").evaluate("element => element.open = false")
            page.locator("#close-government-workspace-btn").click()
            page.locator("#location-search").fill("Rutherford County")
            page.locator("#search-btn").click()
            page.wait_for_function("document.getElementById('intelligence-context').textContent.includes('Rutherford')")
            page.wait_for_function("Math.abs(window.gvaiViewer.camera.positionCartographic.longitude - (-86.4 * Math.PI / 180)) < .01")
        print("Desktop/mobile AI audience, real camera movement, shortlist, follow-up context, Why Here and executable-action rejection verified")
        def submit_question(message):
            page.wait_for_function("!document.querySelector('#regional-ask-form button').disabled")
            page.locator("#regional-question").fill(message)
            page.locator("#regional-ask-form button").click()
            page.wait_for_function("!document.querySelector('#regional-ask-form button').disabled")

        for width, height in [(1440, 900), (390, 844)]:
            print("Starting decision journey", width, flush=True)
            page.set_viewport_size({"width": width, "height": height})
            page.locator("#intelligence-guide").evaluate("element => element.open = true")
            page.wait_for_function("!document.querySelector('#regional-ask-form button').disabled")
            if page.locator("#intelligence-clear").is_visible():
                page.locator("#intelligence-clear").click()
            api_mode["actions"] = [
                {"type": "set_audience", "audience": "business"},
                {"type": "start_investigation", "investigation_type": "business_expansion", "question": "Open a pest control office between Nashville and Chattanooga?"},
                {"type": "set_criteria", "criteria": [
                    {"key": "geography", "value": "Nashville to Chattanooga", "priority": "constraint", "direction": "inspect"},
                    {"key": "distance_radius", "value": {"miles": 100, "center": "Nashville"}, "priority": "constraint", "direction": "inspect"},
                    {"key": "occupations", "value": [{"code": "37-2021.00", "workers": 30}, {"code": "41-3091.00", "workers": 5},
                                                    {"code": "11-1021.00", "workers": 3}], "priority": "constraint", "direction": "inspect"},
                    {"key": "labor_force", "value": "Deeper labor pool", "priority": "primary", "direction": "higher"},
                    {"key": "housing_pressure", "value": "Less housing pressure", "priority": "secondary", "direction": "lower"},
                    {"key": "workforce_availability", "value": "Occupation workforce availability", "priority": "secondary", "direction": "higher"}]},
                {"type": "add_candidate", "query": "Hamilton County, Tennessee"},
                {"type": "compare_candidates"},
                {"type": "focus_candidate", "region_id": "US:county:47065"}]
            before = len(investigations)
            submit_question("Open a pest control branch: 30 workers in 37-2021.00, 5 in 41-3091.00 and 3 in 11-1021.00 within 100 miles of Nashville. Prioritize the deeper labor pool over lower housing pressure; compare Rutherford and Hamilton.")
            assert len(investigations) == before + 2, "Exactly one automatic continuation is allowed"
            current = investigations[-1]["investigation"]
            assert current["type"] == "business_expansion"
            assert len(current["candidates"]) == 2
            assert current["criteria"][2]["value"][0]["workers"] == 30
            assert "PRIVATE_PROFILE_SENTINEL" not in json.dumps(investigations[-1])
            page.wait_for_function("Math.abs(window.gvaiViewer.camera.positionCartographic.longitude - (-85.2 * Math.PI / 180)) < .01")
            panel = page.locator("#intelligence-investigation-content")
            assert "Rutherford County, Tennessee leads" in panel.inner_text()
            assert "occupation" in panel.inner_text()
            assert "unverified" in panel.inner_text()
            assert "Could change if" in panel.inner_text()
            api_mode["actions"] = []
            panel.locator('[data-candidate-action="remove_candidate"][data-region-id="US:county:47065"]').click()
            assert panel.locator('[data-candidate-action="focus_candidate"]').count() == 1
            assert "Reassess before relying" in panel.inner_text()
            api_mode["actions"] = [{"type": "add_candidate", "query": "Hamilton County, Tennessee"}, {"type": "compare_candidates"}]
            submit_question("Add Hamilton back to the shortlist.")
            assert panel.locator('[data-candidate-action="focus_candidate"]').count() == 2
            api_mode["actions"] = []
            submit_question("Why is Rutherford ahead, and what would change that recommendation?")
            assert "Rutherford County, Tennessee leads" in panel.inner_text()
            panel.locator("[data-criteria-editor]").evaluate("element => element.open = true")
            panel.locator('[data-criterion-key="labor_force"][data-criterion-field="priority"]').select_option("secondary")
            panel.locator('[data-criterion-key="housing_pressure"][data-criterion-field="priority"]').select_option("primary")
            assert "Reassess before relying" in panel.inner_text()
            submit_question("Use my updated visible priorities: housing is now primary, labor-force size secondary. Reassess.")
            assert "Hamilton County, Tennessee leads" in panel.inner_text()
            assert "GVAI Score" not in panel.inner_text()
            api_mode["actions"] = [{"type": "add_candidate", "query": "Springfield"}]
            page.locator("#regional-question").fill("What about Springfield?")
            page.locator("#regional-ask-form button").click()
            choice = page.locator("#intelligence-place-choice")
            page.wait_for_selector("#intelligence-place-choice:not([hidden])")
            assert choice.locator("[data-place-choice]").count() == 2
            assert page.locator("#regional-ask-form button").is_disabled()
            choice.locator('[data-place-choice="0"]').click()
            page.wait_for_function("!document.querySelector('#regional-ask-form button').disabled")
            assert investigations[-1]["investigation"]["criteria"][4]["priority"] == "primary"
            assert not choice.is_visible()
            panel.locator("[data-criteria-editor]").evaluate("element => element.open = false")
            panel.locator("p").first.scroll_into_view_if_needed()
            assert panel.evaluate("element => element.scrollWidth <= element.clientWidth + 1")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"decision-{width}.png"))
            api_mode["actions"] = []
            page.locator("#intelligence-clear").click()
            page.locator("#intelligence-guide").evaluate("element => element.open = false")
            page.locator("#close-business-workspace-btn").click()
        print("Desktop/mobile criteria, priority-sensitive evidence read, candidate removal, disambiguation and bounded continuation verified", flush=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#intelligence-guide").evaluate("element => element.open = true")
        page.locator("#regional-ask-pane").evaluate("element => element.open = true")
        page.locator("#intelligence-comparison").evaluate("element => element.open = true")
        api_mode["hold_occupation"] = True
        api_mode["actions"] = [{"type": "open_occupation", "occupation_code": "15-1252.00"},
            {"type": "set_audience", "audience": "business"}]
        page.locator("#regional-question").fill("Open the public occupation evidence.")
        page.locator("#regional-ask-form button").click()
        page.wait_for_function("window.__heldOccupation === true")
        page.locator('[data-remove-region="US:county:47065"]').click()
        pending["occupation"].pop().fulfill(json={"ok": True, "profile": occupation("15-1252.00")})
        page.wait_for_function("document.getElementById('intelligence-action-status').textContent.includes('set audience: stale')")
        assert "open occupation: stale" in page.locator("#intelligence-action-status").inner_text()
        assert not page.locator("#business-workspace").is_visible()
        api_mode["hold_occupation"] = False
        api_mode["actions"] = []
        page.locator("#intelligence-guide").evaluate("element => element.open = false")
        print("User shortlist changes during occupation loading cannot reauthorize stale AI actions", flush=True)
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
                if audience == "laborers":
                    page.locator("#stex-occupation-select").select_option("37-2021.00")
                    page.wait_for_function("document.getElementById('stex-score').textContent === '25.0'")
                    page.locator("#stex-task-audit summary").first.click()
                    assert "Lower-rated structural exposure" in page.locator("#regional-task-patterns").inner_text()
                    assert "not probabilities or guarantees" in page.locator("#regional-task-patterns").inner_text()
                    page.locator("#stex-task-audit summary").first.click()
                    page.locator('.laborers-stage-nav [data-worker-stage-target="live-jobs"]').click()
                    page.locator("#live-jobs-btn").click()
                    page.wait_for_function("document.getElementById('live-jobs-content').textContent.includes('Synthetic opening')")
                    assert "Synthetic provider" in page.locator("#live-jobs-content").inner_text()
                    assert "Austin, Texas" in panel.locator(".regional-jobs-signal").inner_text()
                    page.locator('.laborers-stage-nav [data-worker-stage-target="my-work"]').click()
                page.locator("#ask-btn").click()
                page.locator("#regional-question").fill("Explain this region and its missing signals.")
                page.locator("#regional-ask-form button").click()
                page.wait_for_function("document.getElementById('regional-ask-reply').textContent.includes('Synthetic model interpretation')")
                assert chat_contexts[-1]["audience"] == audience
                assert chat_contexts[-1]["region"]["id"] == "US:county:47149"
                assert chat_contexts[-1]["sources"]["acs"]["vintage"] == 2024
                assert "PRIVATE_PROFILE_SENTINEL" not in json.dumps(chat_contexts[-1])
                assert "PRIVATE_PROFILE_SENTINEL" not in json.dumps(investigations[-1])
                page.locator("#intelligence-guide").evaluate("element => element.open = false")
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
                    window.gvaiViewer.scene.requestRender();
                    window.gvaiViewer.render();
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
            page.locator(".exploration-map-tools > summary").click()
            page.locator("#globe-zoom-in").click()
            page.locator("#globe-zoom-out").click()
            page.locator(".exploration-map-tools > summary").click()
            print(width, "globe colored pixels", pixels)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#audience-laborers-btn").click()
        page.locator("#ask-btn").click()
        page.locator("#regional-question").fill("Explain this region.")
        api_mode["hold_chat"] = True
        with page.expect_request("**/api/chat"):
            page.locator("#regional-ask-form button").click()
        page.locator("#switch-business").click()
        assert pending["chat"]
        with page.expect_response("**/api/chat"):
            pending["chat"].pop().fulfill(json={"ok": True, "reply": "STALE_REPLY_MUST_NOT_RENDER"})
        assert "STALE_REPLY_MUST_NOT_RENDER" not in page.locator("#regional-ask-reply").text_content()
        api_mode["hold_chat"] = False
        api_mode["hold_business"] = True
        with page.expect_request("**/api/business/workforce-intelligence?*"):
            page.locator("#business-workforce-form button").click()
        page.locator("#location-search").fill("France")
        page.locator("#search-btn").click()
        page.wait_for_function("document.querySelector('#business-workspace [data-region-label]').textContent === 'France'")
        assert pending["business"]
        with page.expect_response("**/api/business/workforce-intelligence?*"):
            pending["business"].pop().fulfill(json=business_fixture)
        assert page.locator("#business-workforce-evidence").text_content() == ""
        assert "No current jobs search" in page.locator("#live-jobs-context").text_content()
        assert "363,000" not in page.locator("#business-workspace [data-regional-brief]").inner_text()
        print("Delayed Ask, foreign-region invalidation, real occupation/task/jobs interactions, and private-profile exclusion verified")
        assert not any("/api/region/labor-intelligence" in url or "/api/stex/regional" in url for url in regional_requests)
        print("Structured Ask and labelled scenarios verified for all 15 audience/viewport combinations")
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8090")
    check_site(parser.parse_args().url)