import os
import pytest

pytestmark=pytest.mark.e2e
BASE=os.getenv("LANDSCOPE_TEST_URL","http://127.0.0.1:8000")
# Public sample parcels in Kłodawa: a recent single-parcel land sale and the ULDK geometry check plot.
EXAMPLES=os.getenv("LANDSCOPE_EXAMPLE_PARCELS","080104_2.0002.27/89,080104_2.0002.1235/4").split(",")


@pytest.fixture
def browser_page():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        pytest.fail("UNAVAILABLE: Playwright: "+str(exc),pytrace=False)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.getenv("LANDSCOPE_CHROMIUM_PATH") or None)
        page=browser.new_page(viewport={"width":1440,"height":1000})
        yield page
        browser.close()


def test_map_filters_empty_state(browser_page):
    page=browser_page
    page.goto(BASE,wait_until="networkidle")
    assert page.title().startswith("działkometr")
    page.locator(".leaflet-container").wait_for()
    page.locator("#open-filters").click()
    page.locator("input[name=place]").fill("NoSuchPlaceRegression")
    page.get_by_role("button",name="Pokaż wyniki").click()
    page.get_by_text("Brak transakcji dla tego widoku i filtrów.").wait_for()
    assert page.locator(".leaflet-tile-loaded").count()>0
    page.screenshot(path="test-results/map.png",full_page=True)


@pytest.mark.real_data
@pytest.mark.online
def test_real_klodawa_history_search_and_boundary(browser_page):
    from landscope.db import connect
    with connect() as db:
        row=db.execute("""SELECT o.parcel_id FROM observation o WHERE o.active
          AND lower(translate(o.address,'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ','acelnoszzacelnoszz')) LIKE '%klodawa%'
          ORDER BY md5(o.parcel_id || '8012026') LIMIT 1""").fetchone()
    assert row,"UNAVAILABLE: brak rzeczywistych rekordów Kłodawy"
    page=browser_page
    page.goto(BASE)
    page.locator("#q").fill(row["parcel_id"])
    page.locator("#q").press("Enter")
    page.locator(f'#card[data-id="{row["parcel_id"]}"]').wait_for(timeout=90000)
    page.locator("#card .sale button").filter(has_text="Pokaż cały akt").first.click()
    page.locator('#card[data-kind="sale"]').wait_for()
    assert page.locator("#card .row[data-key='sale.0.transaction.price']").count()==1
    # The card is rendered before the asynchronous camera movement and map refresh finish.
    page.locator(".leaflet-overlay-pane path").first.wait_for(state="attached", timeout=15000)
    assert page.locator(".leaflet-overlay-pane path").count()>0


@pytest.mark.real_data
@pytest.mark.online
def test_example_parcels_every_value_desktop_and_phone():
    from landscope.uicheck import run
    report=run(EXAMPLES,BASE,"test-results/ui")
    problems=[f"[{v['viewport']}] {v['parcel']}: {f}" for v in report["views"] for f in v["failures"]]
    cards=[v for v in report["views"] if v["parcel"] in EXAMPLES]
    assert len(cards)==4*len(EXAMPLES) and all(v["checked"]>=25 for v in cards)
    assert not problems,"\n".join(problems[:30])


@pytest.mark.real_data
@pytest.mark.online
def test_address_search_finds_parcel(browser_page):
    page=browser_page
    page.goto(BASE)
    page.locator("#q").fill("Kłodawa, Gorzowska 40")
    page.locator("#q").press("Enter")
    page.wait_for_selector('#card[data-kind="parcel"]',timeout=90000)
    assert "Gorzowska 40" in page.locator("#card .row[data-key='parcel.address_point'] .row-value").inner_text()


@pytest.mark.real_data
@pytest.mark.online
def test_pagination_sort_favorite_and_draw_area(browser_page):
    page=browser_page
    page.goto(BASE,wait_until="domcontentloaded")
    page.wait_for_function("window.landscope && window.landscope.map")
    page.wait_for_selector("#transactions .tx",timeout=60000)
    page.locator("#next").click()
    page.wait_for_timeout(800)
    assert page.locator("#transactions .tx").count()>0
    page.locator("#sort").select_option("price:asc")
    page.wait_for_timeout(800)
    page.locator("#q").fill("080104_2.0002.27/89")
    page.locator("#q").press("Enter")
    page.wait_for_selector('#card[data-id="080104_2.0002.27/89"]',timeout=90000)
    if page.get_by_role("button",name="Usuń z moich działek").count():
        page.get_by_role("button",name="Usuń z moich działek").click()
        page.wait_for_timeout(600)
    page.locator("#fav-label").fill("Checklista")
    page.get_by_role("button",name="★ Zapisz").click()
    page.wait_for_selector("text=Usuń z moich działek",timeout=15000)
    page.locator("#back").click()
    page.wait_for_timeout(400)
    page.locator("#draw-area").click()
    box=page.locator("#map").bounding_box()
    page.mouse.click(box["x"]+220,box["y"]+220)
    page.mouse.click(box["x"]+300,box["y"]+220)
    page.mouse.click(box["x"]+260,box["y"]+300)
    page.locator("#finish-area").click()
    page.wait_for_timeout(1200)
    assert page.locator("#total").inner_text()!=""
    page.locator("#clear-area").click()
    page.wait_for_timeout(400)
    for value in ("unbuilt","built","unknown"):
        page.locator(f"input[name=cat][value={value}]").uncheck()
    page.get_by_text("Zaznacz co najmniej jedną kategorię w legendzie.").wait_for()
    assert page.locator("#legend-median").inner_text()=="brak"
    assert page.locator("#stats").inner_text().startswith("Brak")
    page.locator("input[name=cat][value=unbuilt]").check()
    page.wait_for_timeout(800)
    page.locator("#select-parcel").click()
    box=page.locator("#map").bounding_box()
    page.mouse.click(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
    page.wait_for_function(
        "() => document.querySelector('#card')?.dataset.kind === 'parcel' || /nie znaleziono|niedostępny/i.test(document.querySelector('#message')?.textContent || '')",
        timeout=30000)


def test_search_shows_message_when_uldk_unavailable(browser_page):
    page=browser_page
    page.route("**/api/parcels/search**", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body='{"detail":"ULDK niedostępny","status":"UNAVAILABLE"}'))
    page.route("**/api/address**", lambda route: route.fulfill(
        status=503, content_type="application/json",
        body='{"detail":"UUG niedostępny","status":"UNAVAILABLE"}'))
    page.goto(BASE, wait_until="domcontentloaded")
    page.locator("#q").fill("080199_1.0001.999")
    page.locator("#q").press("Enter")
    page.get_by_text("ULDK niedostępny").wait_for(timeout=15000)
