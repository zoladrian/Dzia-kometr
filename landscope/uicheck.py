"""Browser check of the real UI: every card value against the API, map labels, clicks and layout, desktop and phone."""
import os
import re
from pathlib import Path
import httpx

VIEWPORTS = {
    "desktop": {"viewport": {"width": 1440, "height": 900}},
    "phone": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True, "device_scale_factor": 2},
    "small-phone": {"viewport": {"width": 320, "height": 568}, "is_mobile": True, "has_touch": True, "device_scale_factor": 2},
    "tablet": {"viewport": {"width": 768, "height": 1024}, "is_mobile": True, "has_touch": True},
}
MOBILE = {"phone", "small-phone", "tablet"}


def slug(value):
    return re.sub(r"[^A-Za-z0-9]+", "-", value)


def expected_rows(card):
    for sec in card["sections"]:
        yield from sec["rows"]
    for sale in card["sales"]:
        for sec in sale["sections"]:
            yield from sec["rows"]


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ")).strip()


CLIPPING_JS = """(scope) => {
  const root = document.querySelector(scope) || document.body, out = [], W = innerWidth;
  for (const n of root.querySelectorAll('*')) {
    if (n.closest('.leaflet-pane, .leaflet-control-container, svg, option') || (n.closest('details:not([open])') && !n.closest('summary'))) continue;
    const s = getComputedStyle(n), r = n.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width === 0 || r.height === 0) continue;
    if (n.closest('[hidden]')) continue;
    const text = (n.innerText || n.value || '').trim().slice(0, 60);
    const own = [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()) || ['INPUT','SELECT','BUTTON'].includes(n.tagName);
    if (!own) continue;
    const clipsX = n.scrollWidth > n.clientWidth + 1 && s.overflowX !== 'visible' && s.overflowX !== 'auto' && s.overflowX !== 'scroll';
    const clipsY = n.scrollHeight > n.clientHeight + 2 && s.overflowY === 'hidden';
    const ellipsis = s.textOverflow === 'ellipsis' && n.scrollWidth > n.clientWidth + 1;
    const scroller = n.closest('.scroll, #details, .panel, #left');
    const outside = !scroller && (r.right > W + 1 || r.left < -1);
    if (clipsX || clipsY || ellipsis || outside)
      out.push(`${n.tagName.toLowerCase()}${n.id ? '#' + n.id : ''}${n.className && typeof n.className === 'string' ? '.' + n.className.split(' ').join('.') : ''} "${text}" ` +
               `(${clipsX ? 'ucięte w poziomie ' : ''}${clipsY ? 'ucięte w pionie ' : ''}${ellipsis ? 'wielokropek ' : ''}${outside ? 'poza ekranem' : ''})`);
  }
  return out;
}"""


COVERED_JS = """(scope) => {
  const root = document.querySelector(scope) || document.body, out = [];
  for (const n of root.querySelectorAll('*')) {
    if (n.closest('.leaflet-pane, svg, option') || (n.closest('details:not([open])') && !n.closest('summary'))) continue;
    const own = [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()) || ['INPUT','SELECT','BUTTON'].includes(n.tagName);
    const r = n.getBoundingClientRect(), s = getComputedStyle(n);
    if (!own || s.visibility === 'hidden' || s.opacity === '0' || r.width === 0 || r.height === 0) continue;
    const x = r.left + Math.min(r.width / 2, 12), y = r.top + r.height / 2;
    // Only the part shown inside every scrolling ancestor; scrolled-away content is not "covered".
    let clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
    for (let a = n.parentElement; a; a = a.parentElement) {
      const as = getComputedStyle(a);
      if (as.overflowX !== 'visible' || as.overflowY !== 'visible') {
        const ar = a.getBoundingClientRect();
        clip = {left: Math.max(clip.left, ar.left), top: Math.max(clip.top, ar.top), right: Math.min(clip.right, ar.right), bottom: Math.min(clip.bottom, ar.bottom)};
      }
    }
    if (x < clip.left || y < clip.top || x > clip.right || y > clip.bottom) continue;
    const blocked = (px, py) => { const t = document.elementFromPoint(px, py); return t && t !== n && !n.contains(t) && !t.contains(n) ? t : null; };
    let top = blocked(x, y);
    if (top) {
      // Content under a sticky header/footer of its own scroller is reachable by scrolling; re-test in view.
      n.scrollIntoView({block: 'center'});
      const q = n.getBoundingClientRect();
      top = blocked(q.left + Math.min(q.width / 2, 12), q.top + q.height / 2);
    }
    if (top) {
      const name = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
      out.push(`"${(n.innerText || n.value || n.placeholder || '').trim().slice(0, 40)}" przykryte przez ${name(top)}`);
    }
  }
  return out;
}"""


def clipped(page, scope="body"):
    return page.evaluate(CLIPPING_JS, scope)


def covered(page, scope="body"):
    return page.evaluate(COVERED_JS, scope)


def lines_of(page, selector):
    """Elements whose text wraps onto more than one line (text nodes only; inline icons do not count)."""
    return page.evaluate("""(sel) => [...document.querySelectorAll(sel)].filter(n => n.getClientRects().length).filter(n => {
        const tops = [], walk = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
        for (let t = walk.nextNode(); t; t = walk.nextNode()) { if (!t.textContent.trim()) continue;
          const rg = document.createRange(); rg.selectNodeContents(t); for (const r of rg.getClientRects()) if (r.width > 1) tops.push(r.top); }
        tops.sort((a, b) => a - b); return tops.length && tops[tops.length - 1] - tops[0] > 4; })
        .map(n => n.innerText.trim()).slice(0, 5)""", selector)


def section_check(layout, page, name, selector):
    cut = clipped(page, selector)
    layout.append({"name": f"{name}: nic nie jest ucięte", "ok": not cut, "detail": "; ".join(cut[:5]) or "OK"})
    hidden = covered(page, selector)
    layout.append({"name": f"{name}: nic nie jest przykryte", "ok": not hidden, "detail": "; ".join(hidden[:5]) or "OK"})


def check_panels(page, base, viewport, out):
    """Every panel once per viewport: visible, nothing cut off, covered or outside the screen."""
    layout = []
    height = VIEWPORTS[viewport]["viewport"]["height"]
    page.goto(base, wait_until="domcontentloaded")
    page.wait_for_function("window.landscope && window.landscope.map")
    page.wait_for_selector("#transactions .tx", state="attached", timeout=60000)
    page.wait_for_timeout(1000)
    shown = page.evaluate("() => [...document.querySelectorAll('[hidden]')].filter(n => n.getClientRects().length).map(n => n.id || n.className)")
    layout.append({"name": "elementy z atrybutem hidden są ukryte", "ok": not shown, "detail": ", ".join(shown) or "OK"})
    section_check(layout, page, "pasek wyszukiwania", ".searchbar")
    section_check(layout, page, "legenda", "#legend")
    if viewport in MOBILE:
        side = page.locator("#side").bounding_box()
        layout.append({"name": "lista schowana do paska u dołu", "ok": bool(side) and side["height"] <= 80 and abs(side["y"] + side["height"] - height) <= 2,
                       "detail": f"pasek y={int(side['y']) if side else None}, h={int(side['height']) if side else None}"})
        page.screenshot(path=str(Path(out) / f"{viewport}-map.png"))
        page.locator("#peek-up").click(); page.wait_for_timeout(450)
        side = page.locator("#side").bounding_box()
        layout.append({"name": "„▲” rozwija listę", "ok": bool(side) and side["height"] >= height * .6, "detail": f"h={int(side['height']) if side else None}"})
        section_check(layout, page, "lista", "#list-view")
        page.screenshot(path=str(Path(out) / f"{viewport}-list.png"))
        page.locator("#peek-up").click(); page.wait_for_timeout(450)
    else:
        boxes = {n: page.locator(s).bounding_box() for n, s in (("lista", "#side"), ("mapa", "#map"), ("pasek", ".searchbar"))}
        ok = all(boxes.values()) and boxes["lista"]["x"] + boxes["lista"]["width"] <= boxes["mapa"]["x"] + 1 and boxes["pasek"]["x"] > boxes["mapa"]["x"]
        layout.append({"name": "lista po lewej, mapa po prawej, pasek wyszukiwania nad mapą", "ok": ok,
                       "detail": ", ".join(f"{k} x={int(v['x'])} w={int(v['width'])}" for k, v in boxes.items() if v)})
        section_check(layout, page, "lista", "#side")
        page.screenshot(path=str(Path(out) / "desktop-overview.png"))
    wraps = lines_of(page, ".tx-side b, .tx-side .unit, .tx-side .more")
    layout.append({"name": "karty listy: cena, cena/m² i „Szczegóły” w jednej linii", "ok": not wraps, "detail": "; ".join(wraps) or "OK"})
    cards = page.locator("#transactions .tx").count()
    layout.append({"name": "lista ma karty transakcji", "ok": cards > 0, "detail": f"{cards} kart"})
    stats = page.locator("#stats .stats-group").count()
    layout.append({"name": "statystyki z medianą w widoku startowym", "ok": stats > 0, "detail": f"{stats} grup"})
    legend = page.locator("#legend-median").inner_text()
    layout.append({"name": "legenda pokazuje medianę i skalę", "ok": "zł" in legend and "zł" in page.locator("#legend-max").inner_text(),
                   "detail": f"mediana {legend}, {page.locator('#legend-min').inner_text()} – {page.locator('#legend-max').inner_text()}"})
    page.locator("#open-filters").click(); page.wait_for_timeout(350)
    drawer = page.locator("#filters-panel").bounding_box()
    layout.append({"name": "„Filtry” otwiera panel filtrów", "ok": bool(drawer) and drawer["height"] > height * .5, "detail": f"h={int(drawer['height']) if drawer else None}"})
    section_check(layout, page, "panel filtrów", "#filters-panel")
    page.screenshot(path=str(Path(out) / f"{viewport}-filters.png"))
    page.locator("#close-filters").click(); page.wait_for_timeout(250)
    layout.append({"name": "zamknięcie filtrów", "ok": not page.locator("#filters-panel").is_visible(), "detail": "panel ukryty"})
    return {"viewport": viewport, "parcel": "(panele)", "checked": 0, "layout": layout, "screenshot": out,
            "failures": [f"UKŁAD: {c['name']} — {c['detail']}" for c in layout if not c["ok"]]}


def check_view(page, base, parcel, viewport, out):
    card = httpx.get(base + "/api/parcel/card", params={"id": parcel}, timeout=60).json()
    failures, layout = [], []
    width, height = VIEWPORTS[viewport]["viewport"]["width"], VIEWPORTS[viewport]["viewport"]["height"]
    scroller = "#details" if viewport in MOBILE else "#side"
    page.goto(base, wait_until="domcontentloaded")
    page.locator(".leaflet-container").wait_for()
    page.wait_for_function("window.landscope && window.landscope.map")
    # Real user flow: type the identifier into "Gdzie?" and press Enter.
    page.locator("#q").fill(parcel)
    page.locator("#q").press("Enter")
    page.wait_for_selector(f'#card[data-id="{parcel}"]', timeout=90000)
    page.wait_for_timeout(700)

    rows = list(expected_rows(card))
    dom_keys = page.eval_on_selector_all("#card .row", "ns => ns.map(n => n.dataset.key)")
    if dom_keys != [r["key"] for r in rows]:
        missing = [r["key"] for r in rows if r["key"] not in dom_keys]
        extra = [k for k in dom_keys if k not in {r["key"] for r in rows}]
        failures.append(f"Kolejność/zakres wierszy różni się od API: brak {missing[:5]}, nadmiar {extra[:5]}")
    for r in rows:
        node = page.locator(f'#card .row[data-key="{r["key"]}"]')
        if node.count() != 1:
            failures.append(f"{r['key']}: znaleziono {node.count()} elementów"); continue
        label = _norm(node.locator(".row-label").inner_text())
        value = _norm(node.locator(".row-value").inner_text())
        status = node.get_attribute("data-status")
        if label != _norm(r["label"]):
            failures.append(f"{r['key']}: etykieta '{label}' ≠ '{r['label']}'")
        if value != _norm(r["value"]):
            failures.append(f"{r['key']} ({r['label']}): wartość '{value}' ≠ API '{r['value']}'")
        if status != r["status"]:
            failures.append(f"{r['key']}: status {status} ≠ {r['status']}")
        node.scroll_into_view_if_needed()
        box = node.locator(".row-value").bounding_box()
        if not box or box["width"] < 1 or box["x"] < -1 or box["x"] + box["width"] > width + 1:
            failures.append(f"{r['key']}: wartość niewidoczna lub poza ekranem {box}")
    cut = clipped(page, "#details")
    layout.append({"name": "karta: nic nie jest ucięte ani poza ekranem", "ok": not cut, "detail": "; ".join(cut[:5]) or "OK"})
    page.locator(scroller).evaluate("n => n.scrollTop = 0")
    page.wait_for_timeout(250)
    hidden = covered(page, "#details")
    layout.append({"name": "karta: widoczna część nie jest przykryta", "ok": not hidden, "detail": "; ".join(hidden[:5]) or "OK"})
    title = _norm(page.locator("#card .card-head h2").inner_text())
    layout.append({"name": "tytuł karty", "ok": title == _norm(card["title"]), "detail": f"'{title}'"})
    tiles = page.locator("#card .row.tile").count()
    layout.append({"name": "kafelki podsumowania", "ok": tiles == 4, "detail": f"{tiles} kafelków"})
    wraps = lines_of(page, "#card .row.tile .row-value")
    layout.append({"name": "kafelki: wartość w jednej linii", "ok": not wraps, "detail": "; ".join(wraps) or "OK"})
    if viewport in MOBILE:
        page.locator(scroller).evaluate("n => n.scrollTop = n.scrollHeight")
        page.wait_for_timeout(200)
        lb = page.locator("#card .row").last.bounding_box()
        layout.append({"name": "koniec karty widoczny po przewinięciu", "ok": bool(lb) and lb["y"] + lb["height"] <= height + 1,
                       "detail": f"dół ostatniego wiersza {int(lb['y'] + lb['height']) if lb else None}, ekran {height}"})
        page.locator(scroller).evaluate("n => n.scrollTop = 0")
        page.locator("#sheet-size").click(); page.wait_for_timeout(350)
        full = page.locator("#side").bounding_box()
        layout.append({"name": "przycisk powiększenia rozwija kartę", "ok": bool(full) and full["y"] <= 20, "detail": f"y={int(full['y']) if full else None}"})
        page.screenshot(path=str(Path(out) / f"{viewport}-{slug(parcel)}-card-full.png"))
        page.locator("#sheet-size").click(); page.wait_for_timeout(350)
        sheet = page.locator("#side").bounding_box()
        on_screen = page.evaluate("""([geometry]) => { const m = window.landscope.map, b = L.geoJSON(geometry).getBounds(), r = m.getContainer().getBoundingClientRect();
            const nw = m.latLngToContainerPoint(b.getNorthWest()), se = m.latLngToContainerPoint(b.getSouthEast());
            const bar = document.querySelector('.searchbar').getBoundingClientRect();
            return {zoom: m.getZoom(), left: r.left + nw.x, right: r.left + se.x, top: r.top + nw.y, bottom: r.top + se.y, barBottom: bar.bottom}; }""", [card["geometry"]])
        fits = bool(sheet) and on_screen["zoom"] >= 16 and on_screen["left"] >= 0 and on_screen["right"] <= width and on_screen["top"] >= on_screen["barBottom"] and on_screen["bottom"] <= sheet["y"]
        layout.append({"name": "działka przybliżona, między paskiem wyszukiwania a kartą", "ok": fits,
                       "detail": f"zoom {on_screen['zoom']}, x {int(on_screen['left'])}–{int(on_screen['right'])}, y {int(on_screen['top'])}–{int(on_screen['bottom'])}, pasek do {int(on_screen['barBottom'])}, karta od {int(sheet['y']) if sheet else None}"})
    shot_card = str(Path(out) / f"{viewport}-{slug(parcel)}-card.png")
    page.screenshot(path=shot_card)

    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    layout.append({"name": "brak przewijania w poziomie", "ok": overflow <= 1, "detail": f"nadmiar {overflow}px"})
    if viewport == "desktop":
        boxes = {n: page.locator(s).bounding_box() for n, s in (("karta", "#details"), ("mapa", "#map"))}
        ok = all(boxes.values()) and boxes["karta"]["x"] + boxes["karta"]["width"] <= boxes["mapa"]["x"] + 1 and boxes["karta"]["width"] >= 480
        layout.append({"name": "karta po lewej (zamiast listy), mapa po prawej", "ok": ok,
                       "detail": ", ".join(f"{k} x={int(v['x'])} w={int(v['width'])}" for k, v in boxes.items() if v)})
    else:
        sheet = page.locator("#side").bounding_box()
        ok = bool(sheet) and sheet["y"] > 150 and abs(sheet["y"] + sheet["height"] - height) <= 2
        layout.append({"name": "karta jako panel od dołu, mapa widoczna nad nią", "ok": ok,
                       "detail": f"karta od y={int(sheet['y']) if sheet else None}, wysokość {int(sheet['height']) if sheet else None}"})
    page.locator("#back").click(); page.wait_for_timeout(450)
    layout.append({"name": "„← Wróć” wraca do listy", "ok": page.evaluate("document.body.dataset.mode") == "list", "detail": page.evaluate("document.body.dataset.mode")})

    # Map: parcel is labelled with its number and a real click inside it opens its card.
    page.evaluate("""([geometry]) => { const g = L.geoJSON(geometry); window.landscope.map.fitBounds(g.getBounds(), {maxZoom: 18, paddingTopLeft: [20, 90], paddingBottomRight: [20, 90]}); }""", [card["geometry"]])
    page.wait_for_timeout(1500)
    page.wait_for_function("document.querySelectorAll('.parcel').length > 0", timeout=30000)
    page.wait_for_timeout(800)
    number = card["number"]
    favorite_label = next((r["value"] for s in card["sections"] for r in s["rows"] if r["key"] == "parcel.label" and r["status"] != "unavailable"), None)
    expected_label = ("★ " + favorite_label) if card["favorite"] and favorite_label != "Zapisana bez etykiety" else (("★ " + number) if card["favorite"] else number)
    labels = [_norm(t) for t in page.eval_on_selector_all(".leaflet-tooltip.parcel-label", "ns => ns.map(n => n.textContent)")]
    layout.append({"name": "podpis działki na mapie", "ok": expected_label in labels,
                   "detail": f"oczekiwano '{expected_label}', widoczne podpisy: {labels[:8]}"})
    label_cut = page.evaluate("""() => [...document.querySelectorAll('.leaflet-tooltip.parcel-label')].filter(n => {
        const r = n.getBoundingClientRect(), m = document.querySelector('#map').getBoundingClientRect();
        const c = (r.left + r.right) / 2, mid = (r.top + r.bottom) / 2;
        return c > m.left + 40 && c < m.right - 40 && mid > m.top + 40 && mid < m.bottom - 40 && (r.left < m.left || r.right > m.right); }).map(n => n.textContent)""")
    layout.append({"name": "podpisy w środku mapy nie wychodzą poza mapę", "ok": not label_cut, "detail": "; ".join(label_cut[:5]) or "OK"})
    tiles = page.locator(".leaflet-tile-loaded").count()
    layout.append({"name": "kafelki mapy", "ok": tiles > 0, "detail": f"{tiles} kafelków"})
    drawn = page.evaluate(f"""() => {{ const n = document.querySelector('path.parcel-{slug(parcel)}'); if (!n) return null;
        const r = n.getBoundingClientRect(); return {{fill: n.getAttribute('fill'), w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top)}}; }}""")
    layout.append({"name": "obrys działki narysowany w realnym rozmiarze, z kolorem", "ok": bool(drawn) and bool(drawn["fill"]) and drawn["w"] >= 15 and drawn["h"] >= 15 and drawn["top"] >= 0,
                   "detail": f"{drawn}"})
    page.evaluate("window.landscope.map.setZoom(window.landscope.map.getZoom() - 1)")
    page.wait_for_timeout(2200)
    refill = page.evaluate(f"""() => {{ const n = document.querySelector('path.parcel-{slug(parcel)}'); return n && n.getAttribute('fill'); }}""")
    layout.append({"name": "kolor działki nie zmienia się po oddaleniu", "ok": bool(drawn) and refill == drawn["fill"], "detail": f"{drawn and drawn['fill']} → {refill}"})
    page.evaluate("window.landscope.map.setZoom(window.landscope.map.getZoom() + 1)")
    page.wait_for_timeout(2200)
    point = page.evaluate("""([geometry]) => {
        const m = window.landscope.map, g = L.geoJSON(geometry), layer = g.getLayers()[0];
        const ring = layer.getLatLngs().flat(3); let best = null;
        // Interior point: centroid when inside, otherwise midpoint between two edge points.
        const c = layer.getBounds().getCenter();
        const inside = (ll) => { let x = ll.lng, y = ll.lat, ins = false;
            for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) { const a = ring[i], b = ring[j];
              if (((a.lat > y) !== (b.lat > y)) && (x < (b.lng - a.lng) * (y - a.lat) / (b.lat - a.lat) + a.lng)) ins = !ins; } return ins; };
        if (inside(c)) best = c; else { for (let i = 0; i < ring.length && !best; i++) for (let j = i + 2; j < ring.length && !best; j++) {
            const mid = L.latLng((ring[i].lat + ring[j].lat) / 2, (ring[i].lng + ring[j].lng) / 2); if (inside(mid)) best = mid; } }
        const p = m.latLngToContainerPoint(best || c), r = m.getContainer().getBoundingClientRect();
        return {x: r.left + p.x, y: r.top + p.y}; }""", [card["geometry"]])
    page.evaluate("document.querySelector('#card').dataset.id = ''")
    shot_map = str(Path(out) / f"{viewport}-{slug(parcel)}-map.png")
    page.screenshot(path=shot_map)
    page.mouse.click(point["x"], point["y"])
    try:
        page.wait_for_selector(f'#card[data-id="{parcel}"]', timeout=20000)
        clicked = True
    except Exception:
        clicked = False
    layout.append({"name": "kliknięcie działki na mapie otwiera jej kartę", "ok": clicked, "detail": f"klik w ({int(point['x'])}, {int(point['y'])})"})
    failures += [f"UKŁAD: {c['name']} — {c['detail']}" for c in layout if not c["ok"]]
    return {"viewport": viewport, "parcel": parcel, "checked": len(rows), "failures": failures, "layout": layout,
            "screenshot": shot_card}


def run(parcels, base="http://127.0.0.1:8000", out="test-results/ui"):
    from playwright.sync_api import sync_playwright
    Path(out).mkdir(parents=True, exist_ok=True)
    views = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.getenv("LANDSCOPE_CHROMIUM_PATH") or None)
        for viewport, options in VIEWPORTS.items():
            context = browser.new_context(locale="pl-PL", **options)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            panels = check_panels(page, base, viewport, out)
            panels["failures"] += [f"Błąd JavaScript: {e}" for e in errors]
            errors.clear()
            views.append(panels)
            for parcel in parcels:
                result = check_view(page, base, parcel, viewport, out)
                result["failures"] += [f"Błąd JavaScript: {e}" for e in errors]
                errors.clear()
                views.append(result)
            context.close()
        browser.close()
    return {"views": views, "failures": sum(len(v["failures"]) for v in views)}
