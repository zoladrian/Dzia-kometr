"use strict";
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
const fmt = v => v == null ? "—" : new Intl.NumberFormat("pl-PL", {maximumFractionDigits: 2}).format(Number(v));
const fmt0 = v => v == null ? "—" : new Intl.NumberFormat("pl-PL", {maximumFractionDigits: 0}).format(Number(v));
const ARE = 100;
const perAr = v => v == null || v === "" ? null : Number(v) * ARE;
const toAres = m2 => m2 == null || m2 === "" ? null : Number(m2) / ARE;
function aresWord(a) {
  if (Math.abs(a - Math.round(a)) > 1e-6) return "ara";
  const n = Math.abs(Math.round(a)), n100 = n % 100, n10 = n % 10;
  if (n10 === 1 && n100 !== 11) return "ar";
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return "ary";
  return "arów";
}
function fmtAres(m2) {
  const a = toAres(m2);
  if (a == null || Number.isNaN(a)) return null;
  const text = Math.abs(a - Math.round(a)) < 1e-6 ? fmt0(a) : fmt(a);
  return text + " " + aresWord(a);
}
function fmtUnit(v) {
  const a = perAr(v);
  return a == null || Number.isNaN(a) ? null : fmt0(a) + " zł/ar";
}
const slug = id => id.replace(/[^A-Za-z0-9]+/g, "-");
const mobile = () => matchMedia("(max-width: 899.98px)").matches;
const STATUS = {confirmed: "źródło", inferred: "wyliczone", unavailable: "brak danych"};
const CATEGORY = {unbuilt: "Niezabudowana", built: "Zabudowana", unknown: "Lokal / inne"};
const NAMES = {rynekPierwotny: "pierwotny", rynekWtorny: "wtórny", unknown: "nieznany", wlasnoscNieruchomosciGruntowej: "własność gruntu",
  uzytkowanieWieczyste: "użytkowanie wieczyste", wlasnoscLokaluWrazZPrawemZwiazanym: "własność lokalu", wlasnoscBudynkuWrazZPrawemZwiazanym: "własność budynku"};
const ICONS = {
  unbuilt: '<svg viewBox="0 0 32 32"><path d="M4 22l9-12 15 4-6 12z"/><path d="M13 10l2 14" stroke-dasharray="2 2"/></svg>',
  built: '<svg viewBox="0 0 32 32"><path d="M3 24l8-12 18 4-6 11z"/><path d="M12 19v-5l4-3 4 3v5z"/></svg>',
  unknown: '<svg viewBox="0 0 32 32"><rect x="8" y="5" width="16" height="22" rx="1"/><path d="M12 10h2M18 10h2M12 15h2M18 15h2M12 20h2M18 20h2"/></svg>',
};
const STOPS = [[0, [59, 91, 219]], [.22, [21, 170, 191]], [.45, [64, 192, 87]], [.68, [250, 176, 5]], [.84, [253, 126, 20]], [1, [224, 49, 49]]];
const GREY = "#9aa0a6";
const LABEL_ZOOM = 16, PAGE = 20;
let map, layer, selection, drawing, polygon = null, vertices = [], mode = null, offset = 0, total = 0, abort;
let selectedIds = [], scale = {min: null, max: null}, index = new Map(), lastSheet = "peek";
let countyItems = [], selectedCounties = ["0801"], countyDraft = new Set(["0801"]);

const message = t => { $("#message").textContent = t || ""; };

async function api(path, opts = {}) {
  const r = await fetch(path, opts), b = await r.json();
  if (!r.ok) throw Error(typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail || b));
  return b;
}
function button(text, fn, cls = "") {
  const n = el("button", text, cls); n.type = "button";
  n.onclick = () => Promise.resolve(fn()).catch(e => message(e.message));
  return n;
}

function colorFor(value, category) {
  if (category && scale.category && category !== scale.category) return GREY;
  if (value == null || scale.min == null) return GREY;
  const lo = Number(scale.min), hi = Number(scale.max);
  const t = hi > lo ? Math.min(1, Math.max(0, (Number(value) - lo) / (hi - lo))) : .5;
  for (let i = 1; i < STOPS.length; i++) {
    const [t1, c1] = STOPS[i], [t0, c0] = STOPS[i - 1];
    if (t <= t1) { const k = (t - t0) / (t1 - t0); return "rgb(" + c0.map((c, j) => Math.round(c + (c1[j] - c) * k)).join(",") + ")"; }
  }
  return "rgb(224,49,49)";
}

/* ---------- Layout state ---------- */
function setMode(next) {
  document.body.dataset.mode = next;
  if (next === "list") { selection && selection.clearLayers(); selectedIds = []; highlight([], false); setSheet(lastSheet === "full" ? "peek" : lastSheet); }
  if (map) setTimeout(() => map.invalidateSize(), 260);
}
function setSheet(next) {
  document.body.dataset.sheet = next;
  const size = $("#sheet-size");
  if (size) size.setAttribute("aria-label", next === "full" ? "Zmniejsz kartę" : "Powiększ kartę");
  $("#peek-up").setAttribute("aria-label", document.body.dataset.mode === "details" ? "Rozwiń kartę działki" : next === "list" ? "Zwiń listę" : "Rozwiń listę");
  if (next === "peek" || next === "list") lastSheet = next;
  if (map) setTimeout(() => map.invalidateSize(), 260);
}
let filterTrigger;
function openFilters(row) {
  filterTrigger = document.activeElement;
  $("#filters-panel").hidden = false; $("#scrim").hidden = false;
  $("#open-filters").setAttribute("aria-expanded", "true");
  $("#side").inert = true; $("#map-wrap").inert = true;
  $$(".frow").forEach(f => f.classList.toggle("focus", f.dataset.row === row));
  const target = row && $(`.frow[data-row=${row}] input, .frow[data-row=${row}] select`);
  (target || $("#close-filters")).focus();
}
function closeFilters() {
  if ($("#filters-panel").hidden) return;
  $("#filters-panel").hidden = true;
  if ($("#counties-panel").hidden) $("#scrim").hidden = true;
  $("#side").inert = false; $("#map-wrap").inert = false;
  $("#open-filters").setAttribute("aria-expanded", "false");
  if (filterTrigger && filterTrigger.isConnected) filterTrigger.focus();
}
function openCounties() {
  filterTrigger = document.activeElement;
  closeFilters();
  countyDraft = new Set(selectedCounties);
  $("#county-q").value = "";
  $("#counties-error").hidden = true;
  $("#counties-panel").hidden = false; $("#scrim").hidden = false;
  $("#open-counties").setAttribute("aria-expanded", "true");
  $("#side").inert = true; $("#map-wrap").inert = true;
  renderCountyList();
  $("#county-q").focus();
}
function closeCounties() {
  if ($("#counties-panel").hidden) return;
  $("#counties-panel").hidden = true; $("#scrim").hidden = true;
  $("#side").inert = false; $("#map-wrap").inert = false;
  $("#open-counties").setAttribute("aria-expanded", "false");
  if (filterTrigger && filterTrigger.isConnected) filterTrigger.focus();
}
function fold(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/ł/g, "l");
}
function capCounty(label) {
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : "Wybierz powiat";
}
function countyWord(n) {
  const n100 = n % 100, n10 = n % 10;
  if (n10 === 1 && n100 !== 11) return "powiat";
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return "powiaty";
  return "powiatów";
}
function regionCaption() {
  const chosen = countyItems.filter(i => selectedCounties.includes(i.code));
  if (!chosen.length) return "Wybierz powiat";
  if (chosen.length === 1) return capCounty(chosen[0].label);
  return chosen.length + " " + countyWord(chosen.length);
}
function syncRegionLabel() {
  const text = regionCaption();
  $("#region-label").textContent = text;
  $("#filters-counties").textContent = text;
  $("#region-source").textContent = "Dane RCN";
}
function renderCountyList() {
  const q = fold($("#county-q").value);
  const root = $("#county-list");
  root.replaceChildren();
  let lastGroup = null, shown = 0;
  for (const item of countyItems) {
    const hay = fold([item.label, item.name, item.code, item.voivodeship, item.hint || ""].join(" "));
    if (q && !hay.includes(q)) continue;
    shown += 1;
    const group = item.pinned && !q ? "Na start" : item.voivodeship;
    if (group && group !== lastGroup) {
      root.append(el("div", group, "county-group"));
      lastGroup = group;
    }
    const row = el("label", null, "county-row" + (item.pinned ? " pinned" : ""));
    const box = document.createElement("input");
    box.type = "checkbox"; box.value = item.code; box.checked = countyDraft.has(item.code);
    box.onchange = () => { if (box.checked) countyDraft.add(item.code); else countyDraft.delete(item.code); };
    const main = el("div");
    main.append(el("b", capCounty(item.label)));
    main.append(el("span", [item.hint, item.voivodeship, item.code].filter(Boolean).join(" · ")));
    const meta = el("small", item.imported ? (fmt0(item.sales) + " aktów") : "brak w bazie");
    row.append(box, main, meta);
    root.append(row);
  }
  $("#counties-status").textContent = shown ? shown + " z " + countyItems.length : "Brak powiatów dla tego wyszukania.";
}
async function loadCounties() {
  const data = await api("/api/counties");
  countyItems = data.items;
  selectedCounties = data.selected.length ? data.selected : ["0801"];
  countyDraft = new Set(selectedCounties);
  syncRegionLabel();
  return data;
}
function flyToSelected() {
  if (!map) return;
  const boxes = countyItems.filter(i => selectedCounties.includes(i.code) && i.bbox);
  if (!boxes.length) return;
  const west = Math.min(...boxes.map(i => i.bbox[0])), south = Math.min(...boxes.map(i => i.bbox[1]));
  const east = Math.max(...boxes.map(i => i.bbox[2])), north = Math.max(...boxes.map(i => i.bbox[3]));
  map.fitBounds([[south, west], [north, east]], {padding: [40, 40], maxZoom: 13, animate: false});
}
async function waitImport() {
  for (let i = 0; i < 180; i++) {
    const data = await api("/api/counties");
    countyItems = data.items;
    selectedCounties = data.selected;
    syncRegionLabel();
    const job = data.importing || {};
    $("#counties-status").textContent = job.message || job.status || "";
    if (job.status === "complete") { message(job.message || "Import zakończony"); return data; }
    if (job.status === "error") throw Error(job.message || "Import nieudany");
    if (job.status !== "running") return data;
    await new Promise(r => setTimeout(r, 2000));
  }
  throw Error("Import trwa dłużej niż 6 minut. Sprawdź logi Dockera i spróbuj ponownie.");
}
async function applyCounties(download) {
  const error = $("#counties-error");
  const codes = [...countyDraft];
  if (!codes.length) {
    error.textContent = "Zaznacz co najmniej jeden powiat.";
    error.hidden = false; return;
  }
  error.hidden = true;
  await api("/api/counties", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({selected: codes})});
  selectedCounties = codes;
  syncRegionLabel();
  const missing = countyItems.filter(i => codes.includes(i.code) && !i.imported).map(i => i.code);
  if (download && missing.length) {
    const take = missing.slice(0, 8);
    message("Pobieram RCN: " + take.join(", "));
    await api("/api/counties/import", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({codes: take})});
    await waitImport();
    await loadCounties();
  }
  closeCounties();
  flyToSelected();
  offset = 0;
  refresh();
}
$("#filters-panel").addEventListener("keydown", e => {
  if (e.key !== "Tab") return;
  const nodes = [...$("#filters-panel").querySelectorAll('button, input, select, [tabindex="0"]')]
    .filter(n => !n.disabled && n.getClientRects().length && (n.type !== "radio" || n.checked));
  const first = nodes[0], last = nodes[nodes.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});
function resetFilters() {
  $("#filters").reset(); $("#q").value = "";
  $("#filter-error").hidden = true;
  offset = 0; refresh();
}
function validateFilters() {
  const form = $("#filters"), error = $("#filter-error");
  for (const [low, high, label] of [
    ["price_min", "price_max", "Cena aktu"], ["unit_min", "unit_max", "Cena za ar"],
    ["area_min", "area_max", "Powierzchnia"], ["date_from", "date_to", "Data sprzedaży"]
  ]) {
    const a = form.elements[low], b = form.elements[high];
    const reversed = low === "date_from" ? a.value > b.value : Number(a.value) > Number(b.value);
    if (a.value && b.value && reversed) {
      error.textContent = `${label}: wartość „od” nie może być większa niż „do”.`;
      error.hidden = false; a.focus(); return false;
    }
  }
  error.hidden = true; return true;
}

/* ---------- Query ---------- */
function params() {
  const p = new URLSearchParams();
  for (const [k, v] of new FormData($("#filters"))) if (v) p.set(k, v);
  const cats = $$("input[name=cat]:checked").map(n => n.value);
  if (cats.length && cats.length < 3 && !p.get("category")) p.set("categories", cats.join(","));
  if (!cats.length) p.set("categories", "none");
  if (p.get("area_min")) p.set("area_min", String(Number(p.get("area_min")) * ARE));
  if (p.get("area_max")) p.set("area_max", String(Number(p.get("area_max")) * ARE));
  if (p.get("unit_min")) p.set("unit_min", String(Number(p.get("unit_min")) / ARE));
  if (p.get("unit_max")) p.set("unit_max", String(Number(p.get("unit_max")) / ARE));
  const b = map.getBounds();
  p.set("bbox", [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(","));
  if (polygon) p.set("polygon", JSON.stringify(polygon));
  if (selectedCounties.length) p.set("counties", selectedCounties.join(","));
  return p;
}

function summarizeFilters() {
  const f = Object.fromEntries(new FormData($("#filters")));
  const range = (a, b, unit) => a && b ? `${fmt0(a)}–${fmt0(b)} ${unit}` : a ? `od ${fmt0(a)} ${unit}` : b ? `do ${fmt0(b)} ${unit}` : null;
  $("#sum-price").textContent = range(f.price_min, f.price_max, "zł") || "Dowolna cena";
  $("#sum-area").textContent = range(f.area_min, f.area_max, "ar") || "Dowolna wielkość";
  const n = ["place", "category", "price_min", "price_max", "unit_min", "unit_max", "area_min", "area_max", "date_from", "date_to", "land_use"].filter(k => f[k]).length;
  $("#filter-count").hidden = !n; $("#filter-count").textContent = n;
}

async function refresh() {
  if (!map) return;
  if (abort) abort.abort();
  abort = new AbortController();
  summarizeFilters();
  const p = params();
  if (p.get("categories") === "none" || !selectedCounties.length) { renderEmpty(); return; }
  const [sort, order] = $("#sort").value.split(":");
  const tp = new URLSearchParams(p); tp.set("limit", PAGE); tp.set("offset", offset); tp.set("sort", sort); tp.set("order", order);
  const mp = new URLSearchParams(p); mp.set("zoom", Math.round(map.getZoom()));
  try {
    message("Pobieranie danych widoku…");
    const [t, g, s] = await Promise.all([
      api("/api/transactions?" + tp, {signal: abort.signal}), api("/api/map?" + mp, {signal: abort.signal}), api("/api/statistics?" + p, {signal: abort.signal})]);
    total = t.total;
    scale = g.scale || {min: null, max: null};
    renderLegend(g.scale);
    renderList(t.items);
    renderMap(g);
    renderStats(s);
    message(g.truncated ? "Za dużo działek w widoku. Przybliż mapę lub zawęź filtry." : "");
  } catch (e) {
    if (e.name !== "AbortError") {
      layer.clearLayers();
      renderStats({note: "", groups: []});
      renderLegend({min: null, max: null, view_median: null, count: 0, label: ""});
      message(e.message);
    }
  }
}

function renderEmpty() {
  layer.clearLayers(); total = 0; renderList([]);
  renderStats({note: "", groups: []});
  renderLegend({min: null, max: null, view_median: null, count: 0, label: ""});
  message("Zaznacz co najmniej jedną kategorię w legendzie.");
}

function renderLegend(sc) {
  $("#legend-cat").textContent = (sc && sc.label) || "Niezabudowane";
  $("#legend-min").textContent = sc && sc.min ? fmt0(perAr(sc.min)) + " zł" : "—";
  $("#legend-max").textContent = sc && sc.max ? fmt0(perAr(sc.max)) + " zł" : "—";
  $("#legend-median").textContent = sc && sc.view_median ? fmt0(perAr(sc.view_median)) + " zł" : "brak";
  $("#legend").title = sc && sc.count ? `Skala: 5.–95. percentyl z ${sc.count} sprzedaży jednej działki kategorii „${sc.label}” w powiecie. Inne kategorie są szare. Mediana: widok mapy.` : "Brak cen za ar.";
}

/* ---------- List ---------- */
function renderList(items) {
  $("#total").textContent = fmt0(total); $("#peek-total").textContent = fmt0(total);
  $("#page").textContent = total ? `${offset + 1}–${Math.min(offset + PAGE, total)} z ${fmt0(total)}` : "";
  $("#prev").disabled = offset === 0; $("#next").disabled = offset + PAGE >= total;
  const root = $("#transactions"); root.replaceChildren();
  const cutoff = new Date(); cutoff.setFullYear(cutoff.getFullYear() - 3);
  for (const row of items) {
    const cat = row.category || "unknown";
    const card = el("article", null, "tx" + (row.sale_date && new Date(row.sale_date) < cutoff ? " old" : ""));
    card.tabIndex = 0; card.dataset.sale = row.id; card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${row.title}, ${row.price == null ? "brak ceny" : fmt0(row.price) + " zł"}. Pokaż szczegóły transakcji`);
    const ico = el("div", null, "tx-ico " + cat); ico.innerHTML = ICONS[cat] || ICONS.unknown;
    ico.append(el("span", cat === "unbuilt" ? "Działka" : cat === "built" ? "Zabudowa" : "Inne"));
    const main = el("div", null, "tx-main");
    main.append(el("b", row.title), el("span", row.locality),
      el("span", [row.matching_area ? fmtAres(row.matching_area) : null, row.parcels_in_act > 1 ? row.parcels_in_act + " działki w akcie" : null].filter(Boolean).join(" · ")));
    const date = el("span", row.sale_date || "Brak daty sprzedaży", "tx-date");
    if (card.classList.contains("old")) date.append(el("small", "ponad 3 lata", "age"));
    main.append(date);
    const side = el("div", null, "tx-side");
    side.append(el("b", row.price == null ? "brak ceny" : fmt0(row.price) + " zł"));
    const unit = row.unit_price ?? null;
    if (unit != null) { const u = el("span", null, "unit"); const sw = el("i"); sw.style.background = colorFor(unit, cat); u.append(sw, fmtUnit(unit)); side.append(u); }
    else if (row.package_unit_price != null) side.append(el("span", "pakiet " + fmtUnit(row.package_unit_price), "unit"));
    side.append(el("span", "Szczegóły", "more"));
    card.append(ico, main, side);
    card.onclick = () => {
      selectedIds = row.parcel_ids || [];
      focusOnGeometry(row.geometry, true, row.focus_geometry);
      openSale(row.id).catch(e => message(e.message));
    };
    card.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); card.click(); } };
    card.onmouseenter = () => highlight(row.parcel_ids, true);
    card.onmouseleave = () => highlight(row.parcel_ids, false);
    root.append(card);
  }
  if (!items.length) {
    const empty = el("div", null, "tx-empty");
    empty.append(el("strong", "Tu jeszcze nie ma wyników"), el("p", "Brak transakcji dla tego widoku i filtrów."),
      el("p", "Przesuń lub oddal mapę albo zmień filtry wyszukiwania."), button("Zmień filtry", () => openFilters()));
    root.append(empty);
  }
}

function highlight(ids, on) {
  const focus = new Set(selectedIds);
  $$(".price-pin-wrap.is-hover").forEach(n => n.classList.remove("is-hover"));
  for (const id of ids || []) {
    const l = index.get(id); if (!l) continue;
    if (l.setStyle) l.setStyle({weight: on || focus.has(id) ? 5 : l.options.baseWeight || 1.5});
    if (on && l.bringToFront) l.bringToFront();
    const pin = document.querySelector(".parcel-pin-" + slug(id));
    if (pin) pin.classList.toggle("is-hover", on);
  }
  $$(".price-pin-wrap.is-selected").forEach(n => n.classList.remove("is-selected"));
  for (const id of focus) {
    const pin = document.querySelector(".parcel-pin-" + slug(id));
    if (pin) pin.classList.add("is-selected");
  }
}

function renderStats(d) {
  $("#stats-note").textContent = d.note;
  const root = $("#stats"); root.replaceChildren();
  const groups = d.groups.filter(g => g.count > 0).slice(0, 6);
  for (const g of groups) {
    const n = el("div", null, "stats-group");
    n.append(el("strong", `${CATEGORY[g.category] || g.category} · ${g.year} · ${g.scope === "package" ? "pakiet" : "jedna działka"}`),
             el("div", `Rynek ${NAMES[g.market] || g.market} · ${NAMES[g.right] || g.right}`, "small"));
    const line = el("div", null, "stats-line");
    line.append(el("span", `mediana ${g.count} akt.`), el("b", fmtUnit(g.median)), el("span", `${fmt0(perAr(g.min))}–${fmt0(perAr(g.max))}`));
    n.append(line);
    const h = el("div", null, "histogram"), max = Math.max(1, ...g.histogram.map(b => b.count));
    for (const b of g.histogram) { const bar = el("i"); bar.style.height = (b.count / max * 100) + "%"; bar.title = `${fmt0(perAr(b.from))}–${fmt0(perAr(b.to))}: ${b.count}`; h.append(bar); }
    n.append(h); root.append(n);
  }
  const hidden = d.groups.filter(g => g.count > 0).length - groups.length;
  if (hidden > 0) root.append(el("p", `+ ${hidden} grup (przybliż mapę, by zawęzić)`, "small"));
  if (!groups.length) root.append(el("p", "Brak uzasadnionej ceny za ar w widoku.", "small"));
}

/* ---------- Map ---------- */
function labelText(p) { return p.favorite ? "★ " + (p.label || p.number) : p.number; }
function hoverText(p) {
  const parts = ["Dz. " + p.number];
  if (p.label) parts.push(p.label);
  if (p.sale_date) parts.push(p.sale_date + (p.sales > 1 ? ` (${p.sales} sprzedaży)` : ""));
  if (p.price_per_m2) parts.push(fmtUnit(p.price_per_m2));
  else if (p.transaction_price) parts.push("akt " + fmt0(p.transaction_price) + " zł");
  if (!p.sales) parts.push("brak sprzedaży w RCN");
  return parts.join(" · ");
}
function priceText(p) {
  if (p.price_per_m2 != null) return fmt0(perAr(p.price_per_m2));
  if (p.transaction_price != null) {
    const v = Number(p.transaction_price);
    if (v >= 1e6) { const m = v / 1e6; return (m % 1 ? m.toFixed(1).replace(".", ",") : String(m)) + " mln"; }
    return Math.round(v / 1e3) + "k";
  }
  return p.number || "·";
}
function priceMarker(ll, p, overParcel) {
  const pin = L.marker(ll, {
    interactive: !overParcel, keyboard: false, zIndexOffset: p.favorite ? 700 : 500,
    icon: L.divIcon({
      html: `<div class="price-pin${p.favorite ? " fav" : ""}${p.price_per_m2 == null ? " none" : ""}" style="background:${colorFor(p.price_per_m2, p.category)}">${priceText(p)}</div>`,
      className: "price-pin-wrap parcel-pin-" + slug(p.parcel_id) + (overParcel ? " over-parcel" : "") + (selectedIds.includes(p.parcel_id) ? " is-selected" : ""),
      iconSize: [0, 0], iconAnchor: [0, 0]})});
  if (!overParcel) {
    pin.bindTooltip(hoverText(p), {sticky: true, className: "hover"});
    pin.on("click", e => { L.DomEvent.stopPropagation(e); openParcel(p.parcel_id).catch(err => message(err.message)); });
  }
  return pin;
}

function renderMap(g) {
  layer.clearLayers(); index = new Map();
  const zoom = map.getZoom(), showNumbers = $("#layer-numbers").checked && zoom >= LABEL_ZOOM;
  const showFav = $("#layer-favorites").checked, outlines = $("#layer-outlines").checked;
  for (const f of g.features) {
    const p = f.properties;
    let l;
    if (p.count) {
      const size = Math.min(54, 30 + Math.log2(p.count) * 4);
      l = L.marker(L.GeoJSON.coordsToLatLng(f.geometry.coordinates), {icon: L.divIcon({
        html: `<div class="cluster" style="width:${size}px;height:${size}px;background:${colorFor(p.median_price_per_m2)}">${p.count}</div>`,
        className: "", iconSize: [size, size]}), title: p.median_price_per_m2 ? `mediana ${fmtUnit(p.median_price_per_m2)}` : ""});
      l.on("click", () => map.setView(l.getLatLng(), Math.min(15, map.getZoom() + 2)));
      layer.addLayer(l); continue;
    }
    if (p.geometry_kind === "favorite_point") {
      if (!showFav) continue;
      l = L.marker(L.GeoJSON.coordsToLatLng(f.geometry.coordinates), {icon: L.divIcon({html: "★ " + (p.label || p.number), className: "fav-pin parcel-pin-" + slug(p.parcel_id)})});
    } else if (p.geometry_kind === "parcel_point" || !outlines || f.geometry.type === "Point") {
      const ll = f.geometry.type === "Point" ? L.GeoJSON.coordsToLatLng(f.geometry.coordinates) : L.geoJSON(f.geometry).getBounds().getCenter();
      l = priceMarker(ll, p, false);
    } else {
      const fill = colorFor(p.price_per_m2, p.category), selected = selectedIds.includes(p.parcel_id);
      const weight = p.favorite ? 3 : 1.5;
      l = L.geoJSON(f.geometry, {style: {color: p.favorite ? "#47317f" : (p.geometry_kind === "parcel_boundary" ? "#1f2330" : fill),
        weight: selected ? 5 : weight, baseWeight: weight, fillColor: p.sales === 0 ? "#47317f" : fill,
        fillOpacity: p.sales === 0 ? .18 : .45, dashArray: p.geometry_kind === "approximate_transaction" ? "4,4" : null,
        className: "parcel parcel-" + slug(p.parcel_id) + (selected ? " selected" : "")}});
      l.options.baseWeight = weight;
      if (showNumbers || (p.favorite && showFav)) l.bindTooltip(labelText(p), {permanent: true, direction: "center", className: "parcel-label" + (p.favorite ? " fav" : "")});
      else l.bindTooltip(hoverText(p), {sticky: true, className: "hover"});
      if (p.price_per_m2 != null || p.transaction_price != null) priceMarker(l.getBounds().getCenter(), p, true).addTo(layer);
    }
    if (p.geometry_kind !== "favorite_point" && l && !l.getTooltip()) l.bindTooltip(hoverText(p), {sticky: true, className: "hover"});
    l.on("click", e => { L.DomEvent.stopPropagation(e); openParcel(p.parcel_id).catch(err => message(err.message)); });
    index.set(p.parcel_id, l.getLayers ? l.getLayers()[0] : l);
    layer.addLayer(l);
  }
}

/* ---------- Card ---------- */
function renderRow(r, tile) {
  const n = el("div", null, "row" + (tile ? " tile" : ""));
  n.dataset.key = r.key; n.dataset.status = r.status;
  n.append(el("span", r.label, "row-label"));
  if (tile && r.sub) n.append(el("span", r.sub, "row-sub"));
  const value = el("span", null, "row-value");
  if (r.link) value.append(button(r.value, () => openParcel(r.link))); else value.textContent = r.value;
  n.append(value);
  if (!tile && r.sub) n.append(el("span", r.sub, "row-sub"));
  const meta = [STATUS[r.status] + (r.source ? " · " + r.source : ""), r.note].filter(Boolean).join(" — ");
  n.append(el("span", meta, "row-meta"));
  return n;
}

function trendChart(rows) {
  const values = rows.map(r => ({year: r.label, v: r.status === "unavailable" ? null : parseFloat(r.value.replace(/[^\d,]/g, "").replace(",", "."))})).filter(x => x.v).reverse();
  if (!values.length) return null;
  const max = Math.max(...values.map(x => x.v)), box = el("div", null, "trend");
  for (const x of values) { const c = el("div"); const bar = el("i"); bar.style.height = (x.v / max * 100) + "%"; c.append(el("b", fmt0(x.v)), bar, el("span", x.year)); box.append(c); }
  return box;
}

function renderSections(parent, sections) {
  for (const s of sections) {
    const box = el("section", null, "card-section"); box.dataset.section = s.key;
    box.append(el("h3", s.title));
    if (s.key === "trend") { const chart = trendChart(s.rows); if (chart) box.append(chart); }
    for (const r of s.rows) box.append(renderRow(r, s.key === "summary"));
    parent.append(box);
  }
}

function renderCard(card, kind) {
  const root = $("#card"); root.replaceChildren();
  root.dataset.kind = kind; root.dataset.id = card.id;
  const hero = el("div", null, "hero card-head");
  const top = el("div", null, "hero-top");
  const back = button("← Wróć", () => setMode("list"), "back"); back.id = "back";
  const actions = el("div", null, "hero-actions");
  const size = el("button", null, "icon-btn"); size.type = "button"; size.id = "sheet-size"; size.setAttribute("aria-label", "Powiększ kartę");
  size.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>';
  size.onclick = () => setSheet(document.body.dataset.sheet === "full" ? "" : "full");
  actions.append(size); top.append(back, actions);
  hero.append(top, el("span", kind === "parcel" ? "Ceny transakcyjne działki" : "Transakcja z RCN", "kicker"), el("h2", card.title));
  if (card.subtitle) hero.append(el("div", card.subtitle, "card-sub"));
  hero.append(el("div", card.id, "card-id"));
  const body = el("div", null, "card-body");
  const bar = el("div", null, "card-actions");
  if (kind === "parcel") {
    if (card.favorite) bar.append(button("Usuń z moich działek", async () => { await api("/api/favorite?id=" + encodeURIComponent(card.id), {method: "DELETE"}); await loadFavorites(); await openParcel(card.id, false); refresh(); }));
    else {
      const input = el("input"); input.placeholder = "Etykieta, np. do porównania"; input.id = "fav-label"; input.setAttribute("aria-label", "Nazwa zapisanej działki");
      bar.append(input, button("★ Zapisz", async () => {
        await api("/api/favorite?id=" + encodeURIComponent(card.id), {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({label: input.value})});
        await loadFavorites(); await openParcel(card.id, false); refresh();
      }, "primary"));
    }
    if (card.geometry_kind !== "parcel_boundary") bar.append(button("Pobierz granicę ULDK", async () => { await api("/api/parcels/search?q=" + encodeURIComponent(card.id)); await openParcel(card.id); }));
  }
  if (card.geometry) bar.append(button("Zobacz na mapie", () => { focusOnGeometry(card.geometry, false, card.focus_geometry); if (mobile()) setSheet("peek"); }));
  body.append(bar);
  renderSections(body, card.sections);
  if (kind === "parcel") body.append(el("h3", card.sales.length ? `Wszystkie dane sprzedaży (${card.sales.length})` : "Brak sprzedaży tej działki w RCN", "sales-head"));
  card.sales.forEach((sale, i) => {
    const art = el("article", null, "sale"); art.dataset.sale = sale.id; art.dataset.index = i;
    art.append(el("h3", sale.title));
    if (kind === "parcel") art.append(button("Pokaż cały akt (wszystkie działki)", () => openSale(sale.id)));
    renderSections(art, sale.sections);
    body.append(art);
  });
  root.append(hero, body);
  $("#details").scrollTop = 0; $("#side").scrollTop = 0;
}

function visibleMapPadding() {
  const mapBox = map.getContainer().getBoundingClientRect();
  if (mobile()) {
    const side = $("#side").getBoundingClientRect();
    return {paddingTopLeft: [28, 90], paddingBottomRight: [28, Math.max(80, Math.round(mapBox.bottom - side.top) + 28)]};
  }
  return {paddingTopLeft: [56, 110], paddingBottomRight: [56, 90]};
}

function boundsOf(geo) {
  if (!geo) return null;
  const b = L.geoJSON(geo).getBounds();
  return b.isValid() ? b : null;
}

function focusOnGeometry(geometry, immediate, cameraGeometry) {
  selection.clearLayers();
  if (!map) return;
  const target = cameraGeometry || geometry;
  if (target) {
    L.geoJSON(target, {interactive: false, style: {color: "#d6336c", weight: 3, fillColor: "#d6336c", fillOpacity: .18, className: "selection"}}).addTo(selection);
  }
  const b = boundsOf(target);
  if (!b) return;
  highlight(selectedIds, true);
  const pad = visibleMapPadding();
  const opts = {...pad, maxZoom: 16};
  if (immediate) map.fitBounds(b, {...opts, animate: false});
  else map.flyToBounds(b, {...opts, duration: .45});
}

async function settleMap() {
  if (mobile()) setSheet("");
  await new Promise(r => setTimeout(r, mobile() ? 450 : 300));
  map.invalidateSize();
  await new Promise(r => setTimeout(r, 350));
}

async function openParcel(id, fit = true) {
  message("Ładowanie karty działki…");
  const card = await api("/api/parcel/card?id=" + encodeURIComponent(id));
  selectedIds = [id];
  renderCard(card, "parcel");
  setMode("details");
  await settleMap();
  if (fit) focusOnGeometry(card.geometry, false, card.focus_geometry);
  message("");
  return card;
}

async function openSale(id) {
  const card = await api("/api/transactions/" + encodeURIComponent(id) + "/card");
  selectedIds = card.parcel_ids || [];
  renderCard(card, "sale");
  setMode("details");
  await settleMap();
  focusOnGeometry(card.geometry, false, card.focus_geometry);
}

async function loadFavorites() {
  const list = await api("/api/favorites"), r = $("#favorites");
  $("#saved-count").textContent = list.length;
  r.replaceChildren();
  for (const p of list) {
    const b = button(null, () => openParcel(p.parcel_id), "fav-item");
    const txt = el("span"); txt.append(el("span", "★ " + (p.label || "Działka")), el("small", p.parcel_id));
    b.append(txt); r.append(b);
  }
  if (!list.length) r.append(el("p", "Brak zapisanych działek. Otwórz kartę i kliknij „Zapisz”.", "small"));
}

/* ---------- Search ---------- */
const PARCEL_ID = /^\d{6}_\d\.\d{4}\./;
async function search(query) {
  query = query.trim();
  if (!query) { refresh(); return; }
  message("Wyszukiwanie…");
  if (PARCEL_ID.test(query)) {
    const d = await api("/api/parcels/search?q=" + encodeURIComponent(query));
    if (!d.items.length) throw Error("Nie znaleziono działki " + query);
    await openParcel(d.items[0].id); return;
  }
  const hasNumber = /\d/.test(query);
  if (hasNumber && !query.includes("/")) {
    try {
      const d = await api("/api/address?q=" + encodeURIComponent(query));
      if (d.items.length) { await openParcel(d.items[0].id); return; }
    } catch (e) { /* not an address point: try obręb + parcel number below */ }
  }
  if (hasNumber) {
    const d = await api("/api/parcels/search?q=" + encodeURIComponent(query));
    if (d.items.length === 1) { await openParcel(d.items[0].id); return; }
    if (d.items.length > 1) { message("Kilka działek pasuje — dopisz gminę, np. „Kłodawa 1235/4”."); return; }
  }
  const b = await api("/api/bounds?place=" + encodeURIComponent(query)).catch(() => null);
  if (!b) { message("Nie znaleziono: " + query); return; }
  $("#filters [name=place]").value = query;
  offset = 0;
  map.fitBounds([[b.bbox[1], b.bbox[0]], [b.bbox[3], b.bbox[2]]], {padding: [40, 40], maxZoom: 15});
  setMode("list"); if (mobile()) setSheet("list");
  message("");
}

/* ---------- Wiring ---------- */
function searchPlaceholder() {
  $("#q").placeholder = mobile() ? "Adres lub nr działki" : "Miejscowość, adres lub nr działki";
}
matchMedia("(max-width: 899.98px)").addEventListener("change", searchPlaceholder);
searchPlaceholder();
$("#search-form").onsubmit = e => { e.preventDefault(); search($("#q").value).catch(err => message(err.message)); };
$$(".seg.wide").forEach(b => b.onclick = () => openFilters(b.dataset.row));
$("#open-filters").onclick = () => openFilters();
$("#close-filters").onclick = closeFilters;
$("#open-counties").onclick = openCounties;
$("#close-counties").onclick = closeCounties;
$("#filters-counties").onclick = openCounties;
$("#county-q").oninput = renderCountyList;
$("#counties-only").onclick = () => applyCounties(false).catch(e => { $("#counties-error").textContent = e.message; $("#counties-error").hidden = false; });
$("#counties-apply").onclick = () => applyCounties(true).catch(e => { $("#counties-error").textContent = e.message; $("#counties-error").hidden = false; });
$("#scrim").onclick = () => { closeFilters(); closeCounties(); };
$("#clear-filters").onclick = resetFilters;
$("#filters").addEventListener("input", () => { $("#filter-error").hidden = true; });
$("#filters").onsubmit = e => { e.preventDefault(); if (!validateFilters()) return; closeFilters(); offset = 0; setMode("list"); if (mobile()) setSheet("list"); refresh(); };
$$(".list-shortcuts button").forEach(b => b.onclick = () => {
  const section = document.getElementById(b.dataset.section); section.open = true;
  section.scrollIntoView({block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
  section.querySelector("summary").focus({preventScroll: true});
});
$$("input[name=cat]").forEach(n => n.onchange = () => { offset = 0; refresh(); });
$$("#layers input").forEach(n => n.onchange = () => refresh());
$("#layers-btn").onclick = () => { const p = $("#layers"); p.hidden = !p.hidden; $("#layers-btn").setAttribute("aria-expanded", String(!p.hidden)); };
$("#sort").onchange = () => { offset = 0; refresh(); };
$("#prev").onclick = () => { offset = Math.max(0, offset - PAGE); refresh(); };
$("#next").onclick = () => { offset += PAGE; refresh(); };
$("#toggle-list").onclick = () => {
  if (mobile()) { setMode("list"); setSheet(document.body.dataset.sheet === "list" ? "peek" : "list"); }
  else { document.body.dataset.mode === "details" ? setMode("list") : (document.body.classList.toggle("side-hidden"), map.invalidateSize()); }
};
$("#peek-up").onclick = () => setSheet(document.body.dataset.mode === "details" ? "" : document.body.dataset.sheet === "list" ? "peek" : "list");
$("#peek-list").onclick = () => { setMode("list"); setSheet("list"); };
function setTool(next) {
  mode = next;
  document.body.classList.toggle("is-drawing", next === "draw");
  document.body.classList.toggle("is-picking", next === "parcel");
  $("#draw-area").classList.toggle("active", next === "draw");
  $("#select-parcel").classList.toggle("active", next === "parcel");
  if (!map) return;
  const drawingNow = next === "draw";
  map.getContainer().classList.toggle("leaflet-crosshair", drawingNow);
  if (drawingNow) { map.dragging.disable(); map.doubleClickZoom.disable(); }
  else { map.dragging.enable(); map.doubleClickZoom.enable(); }
}

function redrawDraft() {
  if (drawing) map.removeLayer(drawing);
  drawing = null;
  if (!vertices.length) return;
  drawing = L.layerGroup().addTo(map);
  if (vertices.length >= 2) {
    L.polygon(vertices, {color: "#47317f", weight: 2, fillColor: "#47317f", fillOpacity: .1, interactive: false}).addTo(drawing);
  }
  vertices.forEach(p => {
    L.circleMarker(p, {radius: 6, color: "#47317f", weight: 2, fillColor: "#fff", fillOpacity: 1, interactive: false}).addTo(drawing);
  });
}

function addVertex(ll) {
  if (mode !== "draw") return;
  if (vertices.length) {
    const last = vertices[vertices.length - 1];
    if (map.latLngToLayerPoint(last).distanceTo(map.latLngToLayerPoint(ll)) < 8) return;
  }
  vertices.push(ll);
  redrawDraft();
  const n = vertices.length;
  const form = n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "wierzchołki" : "wierzchołków";
  message(n < 3
    ? `Wierzchołek ${n} z 3. Kliknij jeszcze ${3 - n}.`
    : `${n} ${form} — „Zakończ obszar” albo podwójne kliknięcie.`);
}

function finishArea() {
  if (vertices.length < 3) { message("Wybierz co najmniej trzy wierzchołki."); return; }
  const ring = vertices.map(p => [p.lng, p.lat]); ring.push(ring[0]);
  polygon = {type: "Polygon", coordinates: [ring]};
  setTool(null);
  $("#finish-area").hidden = true; $("#clear-area").hidden = false;
  offset = 0; message(""); refresh();
}

function cancelDraw() {
  if (mode !== "draw") return;
  vertices = [];
  if (drawing) { map.removeLayer(drawing); drawing = null; }
  if (polygon) redrawDraftFromPolygon();
  setTool(null);
  $("#finish-area").hidden = true;
  $("#clear-area").hidden = !polygon;
  message(polygon ? "Rysowanie przerwane; poprzedni obszar zostaje." : "");
}

function redrawDraftFromPolygon() {
  if (!polygon || !polygon.coordinates) return;
  vertices = polygon.coordinates[0].slice(0, -1).map(([lng, lat]) => L.latLng(lat, lng));
  redrawDraft();
}

$("#select-parcel").onclick = () => {
  cancelDraw();
  setTool("parcel");
  message("Kliknij wewnątrz działki na mapie.");
  if (mobile()) { setMode("list"); setSheet("peek"); }
};
$("#draw-area").onclick = () => {
  if (!map) return;
  if (mode === "draw") { cancelDraw(); return; }
  vertices = [];
  if (drawing) map.removeLayer(drawing);
  drawing = null;
  $("#finish-area").hidden = false;
  $("#clear-area").hidden = !polygon;
  setTool("draw");
  if (mobile()) { setMode("list"); setSheet("peek"); }
  message("Klikaj wierzchołki na mapie. Przesuwanie jest wyłączone do zakończenia. Esc anuluje.");
};
$("#finish-area").onclick = finishArea;
$("#clear-area").onclick = () => {
  polygon = null; vertices = []; setTool(null);
  if (drawing) map.removeLayer(drawing); drawing = null;
  $("#finish-area").hidden = true; $("#clear-area").hidden = true; offset = 0; refresh();
};
addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!$("#counties-panel").hidden) { closeCounties(); return; }
  if (!$("#filters-panel").hidden) { closeFilters(); return; }
  closeFilters(); closeCounties();
  if (mode === "draw") { cancelDraw(); return; }
  if (mode === "parcel") setTool(null);
  if (document.body.dataset.mode === "details") setMode("list");
});

async function start() {
  setSheet("peek");
  try { await loadCounties(); } catch (e) { message(e.message); }
  if (window.L) {
    const home = countyItems.find(i => i.code === (selectedCounties[0] || "0801"));
    map = L.map("map", {zoomControl: false, preferCanvas: false, maxZoom: 19}).setView(home ? [home.bbox[1] + 0.32, home.bbox[0] + 0.32] : [52.786, 15.214], 13);
    L.control.zoom({position: "bottomleft"}).addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);
    layer = L.featureGroup().addTo(map); selection = L.featureGroup().addTo(map);
    window.landscope = {map, openParcel, refresh};
    let timer;
    map.on("moveend", () => { clearTimeout(timer); offset = 0; timer = setTimeout(refresh, 250); });
    map.getContainer().addEventListener("click", e => {
      if (mode !== "draw" || e.button) return;
      e.preventDefault(); e.stopPropagation();
      addVertex(map.mouseEventToLatLng(e));
    }, true);
    map.on("dblclick", e => { if (mode === "draw") { L.DomEvent.stop(e); finishArea(); } });
    map.on("click", async e => {
      if (mode === "draw") return;
      else if (mode === "parcel") {
        setTool(null);
        try {
          const r = await api("/api/parcels/at-point?lon=" + e.latlng.lng + "&lat=" + e.latlng.lat);
          if (!r.items.length) throw Error("Nie znaleziono działki w tym punkcie.");
          await openParcel(r.items[0].id, false); refresh();
        } catch (err) { message(err.message); }
      }
    });
    refresh();
  } else { $("#map").textContent = "Biblioteka mapy niedostępna. Uruchom: python scripts/fetch_assets.py"; message("Mapa wymaga lokalnych plików Leaflet."); }
  try { await api("/api/health"); const c = await api("/api/counts"); $(".brand-sub").textContent = `${fmt0(c.sale)} transakcji w bazie / ${fmt0(c.parcel)} działek`; }
  catch (e) { $(".brand-sub").textContent = "Baza niedostępna"; }
  try { await loadFavorites(); } catch (e) { $("#favorites").textContent = "Baza niedostępna"; }
  try {
    const s = await api("/api/sources"), r = $("#sources"); r.replaceChildren();
    for (const item of s) { const d = el("div", null, "source"); d.append(el("strong", item.source + " · " + item.status, item.status), el("span", item.reason || ""), el("div", item.checked_at || "Nie sprawdzono")); r.append(d); }
  } catch (e) { $("#sources").textContent = e.message; }
  const wanted = new URLSearchParams(location.search).get("parcel");
  if (wanted) openParcel(wanted).catch(e => message(e.message));
}
start();
