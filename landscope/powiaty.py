"""TERYT counties the user can load locally. Gorzowski and miński (Arynów) stay pinned first."""
import json
import threading
from pathlib import Path
from .db import connect
from .domain import ContractError

PINNED = ("0801", "1412")
DEFAULT_SELECTED = ["0801"]
HINTS = {
    "0801": "powiat ziemski, bez miasta Gorzów Wielkopolski",
    "1412": "Arynów, gmina Mińsk Mazowiecki",
}
NAMES = {
    "0801": "gorzowski",
    "1412": "miński",
    "0861": "Gorzów Wielkopolski",
}
VOIVODESHIP = {
    "02": "dolnośląskie", "04": "kujawsko-pomorskie", "06": "lubelskie", "08": "lubuskie",
    "10": "łódzkie", "12": "małopolskie", "14": "mazowieckie", "16": "opolskie",
    "18": "podkarpackie", "20": "podlaskie", "22": "pomorskie", "24": "śląskie",
    "26": "świętokrzyskie", "28": "warmińsko-mazurskie", "30": "wielkopolskie", "32": "zachodniopomorskie",
}
BBOX_PAD = 0.32

_catalog = None
_job = {"status": "idle", "codes": [], "current": None, "message": "", "reports": []}
_job_lock = threading.Lock()


def _load():
    global _catalog
    if _catalog is None:
        raw = json.loads((Path(__file__).parent / "counties.json").read_text(encoding="utf-8"))
        _catalog = raw["counties"]
    return _catalog


def known(code):
    return any(item["code"] == code for item in _load())


def parse_codes(values):
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    codes = []
    for code in values:
        if not isinstance(code, str) or len(code) != 4 or not code.isdigit() or not known(code):
            raise ContractError("Nieznany kod powiatu: " + str(code))
        if code not in codes:
            codes.append(code)
    return codes


def bbox_of(item):
    lat, lon = item["lat"], item["lon"]
    return [round(lon - BBOX_PAD, 4), round(lat - BBOX_PAD, 4), round(lon + BBOX_PAD, 4), round(lat + BBOX_PAD, 4)]


def label(item):
    name = NAMES.get(item["code"], item["name"])
    if item["city"]:
        return name
    if name[:1].isupper() and name[1:].islower():
        name = name.lower()
    return "powiat " + name


def catalog():
    items = list(_load())
    pinned = {code: None for code in PINNED}
    rest = []
    for item in items:
        hint = HINTS.get(item["code"])
        if not hint and item["city"]:
            hint = "miasto na prawach powiatu"
        row = {
            "code": item["code"], "name": NAMES.get(item["code"], item["name"]),
            "label": label(item), "city": item["city"],
            "voivodeship": VOIVODESHIP.get(item["code"][:2], ""),
            "hint": hint, "bbox": bbox_of(item),
            "pinned": item["code"] in pinned,
        }
        if item["code"] in pinned:
            pinned[item["code"]] = row
        else:
            rest.append(row)
    rest.sort(key=lambda r: (r["voivodeship"], r["label"]))
    return [pinned[code] for code in PINNED if pinned[code]] + rest


def _ensure_settings(db):
    db.execute("""CREATE TABLE IF NOT EXISTS app_setting (
        key text PRIMARY KEY, value jsonb NOT NULL)""")


def selected_codes():
    with connect() as db:
        _ensure_settings(db)
        row = db.execute("SELECT value FROM app_setting WHERE key='counties'").fetchone()
    if not row or not isinstance(row["value"], list) or not row["value"]:
        return list(DEFAULT_SELECTED)
    try:
        return parse_codes(row["value"])
    except ContractError:
        return list(DEFAULT_SELECTED)


def save_selected(codes):
    codes = parse_codes(codes)
    if not codes:
        raise ContractError("Zaznacz co najmniej jeden powiat")
    from psycopg.types.json import Jsonb
    with connect() as db:
        _ensure_settings(db)
        db.execute("""INSERT INTO app_setting(key,value) VALUES ('counties',%s)
            ON CONFLICT (key) DO UPDATE SET value=excluded.value""", (Jsonb(codes),))
    return codes


def county_stats():
    with connect() as db:
        rows = db.execute("""SELECT county,
            count(*) FILTER (WHERE active) AS observations,
            count(DISTINCT sale_id) FILTER (WHERE active) AS sales
            FROM observation GROUP BY county""").fetchall()
        latest = db.execute("""SELECT DISTINCT ON (county) county,status,finished_at,report
            FROM import_run ORDER BY county, started_at DESC""").fetchall()
    stats = {r["county"]: {"observations": r["observations"], "sales": r["sales"]} for r in rows}
    for row in latest:
        stats.setdefault(row["county"], {"observations": 0, "sales": 0})
        stats[row["county"]]["import_status"] = row["status"]
        stats[row["county"]]["imported_at"] = str(row["finished_at"]) if row["finished_at"] else None
    return stats


def job_status():
    with _job_lock:
        return dict(_job)


def overview():
    stats = county_stats()
    selected = selected_codes()
    job = job_status()
    items = []
    for item in catalog():
        info = stats.get(item["code"], {"observations": 0, "sales": 0})
        items.append({**item, "selected": item["code"] in selected,
                      "observations": info.get("observations") or 0,
                      "sales": info.get("sales") or 0,
                      "imported": (info.get("observations") or 0) > 0,
                      "import_status": info.get("import_status"),
                      "imported_at": info.get("imported_at")})
    return {"selected": selected, "importing": job, "items": items,
            "defaults": list(PINNED)}


def import_county_data(code, force=False):
    code = parse_codes([code])[0]
    stats = county_stats().get(code) or {}
    if not force and (stats.get("observations") or 0) > 0:
        return {"county": code, "skipped": True, "reason": "Dane tego powiatu są już w bazie"}
    if code == "0801":
        from .county import import_county
        report = import_county(code)
        report["source_kind"] = "gml_powiatu"
    else:
        from .importer import import_rcn
        report = import_rcn(code)
        report["source_kind"] = "wfs"
    report["county"] = code
    return report


def start_import(codes, force=False):
    codes = parse_codes(codes)
    with _job_lock:
        if _job["status"] == "running":
            raise ContractError("Import już trwa")
        _job.update({"status": "running", "codes": codes, "current": codes[0],
                     "message": "Pobieranie " + codes[0], "reports": []})
    thread = threading.Thread(target=_run_import, args=(codes, force), daemon=True)
    thread.start()
    return job_status()


def _run_import(codes, force):
    reports = []
    try:
        for code in codes:
            with _job_lock:
                _job.update({"current": code, "message": "Pobieranie powiatu " + code})
            reports.append(import_county_data(code, force=force))
        save_selected(list(dict.fromkeys(selected_codes() + codes)))
        with _job_lock:
            _job.update({"status": "complete", "current": None,
                         "message": "Import zakończony", "reports": reports})
    except Exception as exc:
        with _job_lock:
            _job.update({"status": "error", "message": str(exc), "reports": reports})
