"""UI regression checks against the running app and real local records; no API mocks."""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from landscope.uicheck import clipped, covered

pytestmark = [pytest.mark.e2e, pytest.mark.real_data]
BASE = os.getenv("LANDSCOPE_TEST_URL", "http://127.0.0.1:8000")
OUT = Path("test-results/design")


@pytest.fixture(scope="module")
def chromium():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.getenv("LANDSCOPE_CHROMIUM_PATH") or None)
        yield browser
        browser.close()


@pytest.mark.parametrize("width,height", [(1440, 900), (1280, 720), (1024, 768), (900, 700),
                                         (768, 1024), (390, 844), (320, 568), (844, 390), (720, 450)])
def test_responsive_panels(chromium, width, height):
    OUT.mkdir(parents=True, exist_ok=True)
    context = chromium.new_context(viewport={"width": width, "height": height}, locale="pl-PL")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(BASE, wait_until="domcontentloaded")
        page.locator("#transactions .tx").first.wait_for(state="attached", timeout=30000)
        expect(page).to_have_title("działkometr — ceny transakcyjne działek")
        assert not clipped(page, ".searchbar")
        assert not covered(page, ".searchbar")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUT / f"{width}x{height}-map.png"))
        if width < 900:
            page.locator("#peek-up").click()
            page.wait_for_timeout(300)
        assert not clipped(page, "#list-view")
        assert not covered(page, "#list-view")
        page.locator("#side" if width >= 900 else "#list-view").evaluate("n => n.scrollTop = 0")
        page.screenshot(path=str(OUT / f"{width}x{height}-list.png"))
        page.locator('[data-section="saved-section"]').click()
        expect(page.locator("#saved-section summary")).to_be_focused()
        expect(page.locator("#saved-section summary")).to_be_in_viewport()
        if width < 900:
            page.locator("#peek-up").click()
            page.wait_for_timeout(300)
        page.locator("#open-filters").click()
        expect(page.locator("#close-filters")).to_be_focused()
        assert not clipped(page, "#filters-panel")
        assert not covered(page, "#filters-panel")
        expect(page.locator("#apply-filters")).to_be_in_viewport()
        page.locator("#filters").evaluate("n => n.scrollTop = 0")
        page.screenshot(path=str(OUT / f"{width}x{height}-filters.png"))
        page.locator("#apply-filters").focus()
        page.keyboard.press("Tab")
        expect(page.locator("#close-filters")).to_be_focused()
        page.keyboard.press("Shift+Tab")
        expect(page.locator("#apply-filters")).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.locator("#filters-panel")).to_be_hidden()
        expect(page.locator("#open-filters")).to_be_focused()
        assert not page.locator("#map-wrap").evaluate("n => n.inert")
        assert not errors
    finally:
        context.close()


def test_filter_range_validation_and_clear(chromium):
    page = chromium.new_page(viewport={"width": 1024, "height": 768})
    try:
        page.goto(BASE, wait_until="domcontentloaded")
        page.locator("#transactions .tx").first.wait_for(timeout=30000)
        page.locator("#open-filters").click()
        page.locator('[name="price_min"]').fill("500000")
        page.locator('[name="price_max"]').fill("100000")
        page.locator("#apply-filters").click()
        expect(page.locator("#filters-panel")).to_be_visible()
        expect(page.locator("#filter-error")).to_contain_text("Cena aktu")
        expect(page.locator("#filter-error")).to_be_in_viewport()
        expect(page.locator('[name="price_min"]')).to_be_focused()
        page.locator("#clear-filters").click()
        expect(page.locator("#filter-error")).to_be_hidden()
        expect(page.locator('[name="price_min"]')).to_have_value("")
        page.locator('[name="place"]').fill("NoSuchPlaceDesignCheck")
        page.locator("#apply-filters").click()
        expect(page.locator(".tx-empty")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Zmień filtry").click()
        page.locator("#clear-filters").click()
        page.locator("#apply-filters").click()
        expect(page.locator("#transactions .tx").first).to_be_visible(timeout=15000)
    finally:
        page.close()


@pytest.mark.parametrize("width,height", [(390, 844), (320, 568), (844, 390), (720, 450)])
def test_mobile_details_collapse_and_restore(chromium, width, height):
    page = chromium.new_page(viewport={"width": width, "height": height}, reduced_motion="reduce")
    try:
        page.goto(BASE + "/?parcel=080104_2.0002.27%2F89", wait_until="domcontentloaded")
        page.locator('#card[data-id="080104_2.0002.27/89"]').wait_for(timeout=30000)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Zobacz na mapie").click()
        expect(page.locator("#details")).to_be_hidden()
        assert page.locator("#side").bounding_box()["height"] <= 80
        page.locator("#peek-up").click()
        expect(page.locator("#details")).to_be_visible()
        page.locator("#sheet-size").click()
        assert page.locator("#side").bounding_box()["y"] <= 20
        assert not clipped(page, "#details")
        page.screenshot(path=str(OUT / f"{width}x{height}-card.png"))
        page.locator("#details").evaluate("n => n.scrollTop = n.scrollHeight")
        expect(page.locator("#card .row").last).to_be_in_viewport()
        page.locator("#details").evaluate("n => n.scrollTop = 0")
        page.locator("#sheet-size").click()
        page.locator("#open-filters").click()
        page.keyboard.press("Escape")
        assert page.locator("body").get_attribute("data-mode") == "details"
    finally:
        page.close()
