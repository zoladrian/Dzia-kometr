"""Archive first, checkpoint downloads, then atomically promote a complete batch."""
import json
import logging
import uuid
from .config import RCN_URL, data_dir
from .db import connect, initialize
from .domain import ContractError, checksum, stable_id, effective_unit_price
from .sources import fetch, archive, rcn_page, rcn_params, rcn_schema, normalize_rcn, utcnow

log = logging.getLogger(__name__)


def save_batch(records, county, run_id=None, source_url=RCN_URL, complete=True):
    from psycopg.types.json import Jsonb
    run_id = run_id or str(uuid.uuid4())
    normalized, rejected = [], []
    seen = {}
    for raw in records:
        try:
            item = normalize_rcn(raw["fields"],raw["feature_id"],raw.get("geometry"))
            if not item["parcel_id"].startswith(county):
                raise ContractError("Rekord poza żądanym powiatem")
            if raw.get("geometry_error"):
                item["issues"].append("invalid_geometry")
            digest = checksum(raw)
            if item["id"] in seen:
                if seen[item["id"]] != digest:
                    raise ContractError("Sprzeczne duplikaty identyfikatora obiektu w jednym imporcie")
                continue
            seen[item["id"]] = digest
            normalized.append((item,raw,digest))
        except ContractError as exc:
            rejected.append((raw,str(exc)))
    # Contradictory transaction versions in the same snapshot must never be merged.
    grouped = {}
    for item,raw,digest in normalized:
        key = item["transaction_id"]
        signature = (item["date"],item["transaction_price"],item["source_version"])
        if key in grouped and grouped[key] != signature:
            raise ContractError("Niespójne pola transakcji w obrębie pobranego zbioru")
        grouped[key] = signature
    report = {"run_id":run_id,"source_rows":len(records),"accepted":len(normalized),"rejected":len(rejected),
              "duplicates":len(records)-len(normalized)-len(rejected),"complete":complete and not rejected}
    with connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",("rcn:"+county,))
        db.execute("INSERT INTO import_run(id,source,county,status) VALUES (%s,%s,%s,'running')",
                   (run_id,source_url,county))
        if complete and not rejected:
            db.execute("UPDATE observation SET active=false WHERE county=%s AND source=%s",(county,source_url))
        for item,raw,digest in normalized:
            tx = item["transaction_id"]
            existing = db.execute("SELECT source_version FROM sale WHERE id=%s",(tx,)).fetchone()
            if existing and existing["source_version"] and item["source_version"] and item["source_version"] < existing["source_version"]:
                raise ContractError("Starsza wersja transakcji nie może nadpisać nowszej")
            db.execute("""INSERT INTO sale(id,namespace,source_id,sale_date,price,source_version) VALUES (%s,%s,%s,%s,%s,%s)
              ON CONFLICT(id) DO UPDATE SET sale_date=excluded.sale_date,price=excluded.price,source_version=excluded.source_version""",
              (tx,item["namespace"],item["transaction_source_id"],item["date"],item["transaction_price"],item["source_version"]))
            identity = item.get("property_identity") if item.get("property_identity") in {"confirmed","unavailable"} else "unavailable"
            source_id = item.get("property_source_id")
            if identity == "confirmed" and source_id:
                prop = stable_id("property",tx,source_id)
            else:
                prop = stable_id("property-observation",item["id"])
            db.execute("""INSERT INTO property(id,sale_id,source_id,identity_status,price,area,category,share,right_type)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
              sale_id=excluded.sale_id,source_id=excluded.source_id,identity_status=excluded.identity_status,
              price=excluded.price,area=excluded.area,category=excluded.category,share=excluded.share,right_type=excluded.right_type""",
              (prop,tx,item.get("property_source_id"),identity,item["property_price"],item["property_area"],item["category"],item["share"],item["right"]))
            db.execute("INSERT INTO parcel(id,number) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                       (item["parcel_id"],item["parcel_id"].split(".")[-1]))
            geometry = json.dumps(item["geometry"]) if item["geometry"] else None
            unit,basis = effective_unit_price(item)
            db.execute("""INSERT INTO observation(id,sale_id,property_id,parcel_id,county,feature_id,source,price,area,category,address,land_use,location,payload,hash,run_id,unit_price,unit_basis)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s,%s,%s)
              ON CONFLICT(id) DO UPDATE SET sale_id=excluded.sale_id,property_id=excluded.property_id,parcel_id=excluded.parcel_id,
              price=excluded.price,area=excluded.area,category=excluded.category,address=excluded.address,land_use=excluded.land_use,
              location=excluded.location,payload=excluded.payload,hash=excluded.hash,run_id=excluded.run_id,fetched_at=now(),active=true,
              unit_price=excluded.unit_price,unit_basis=excluded.unit_basis""",
              (item["id"],tx,prop,item["parcel_id"],county,item["feature_id"],source_url,item["price"],item["area"],
               item["category"],item["address"],item["land_use"],geometry,Jsonb(item),digest,run_id,unit,basis))
            db.execute("""INSERT INTO raw_record(observation_id,hash,run_id,source_url,payload) VALUES (%s,%s,%s,%s,%s)
                          ON CONFLICT(observation_id,hash) DO NOTHING""",(item["id"],digest,run_id,source_url,Jsonb(raw)))
        for raw,reason in rejected:
            db.execute("INSERT INTO rejected_record(run_id,feature_id,reason,raw) VALUES (%s,%s,%s,%s)",
                       (run_id,raw.get("feature_id"),reason,Jsonb(raw)))
        db.execute("DELETE FROM property p WHERE NOT EXISTS (SELECT 1 FROM observation o WHERE o.property_id=p.id)")
        db.execute("UPDATE import_run SET status=%s,finished_at=now(),report=%s WHERE id=%s",
                   ("complete" if report["complete"] else "partial",Jsonb(report),run_id))
    return report


def import_rcn(county="0801", resume=None, page_size=500, max_pages=10000):
    initialize()
    folder = data_dir() / "imports" / (resume or str(uuid.uuid4()))
    folder.mkdir(parents=True,exist_ok=True)
    manifest_file = folder / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if manifest["county"] != county or manifest["page_size"] != page_size:
            raise ContractError("Parametry wznowienia różnią się od pierwotnego importu")
    else:
        schema = fetch(RCN_URL,{"service":"WFS","version":"2.0.0","request":"DescribeFeatureType","typenames":"ms:dzialki"})
        archive(schema,"rcn")
        rcn_schema(schema.content)
        manifest = {"county":county,"page_size":page_size,"pages":[],"created_at":utcnow(),"done":False}
    all_records,seen = [],set()
    matched = None
    start = 0
    for index in range(max_pages):
        if index < len(manifest["pages"]):
            content = __import__("pathlib").Path(manifest["pages"][index]).read_bytes()
        else:
            response = fetch(RCN_URL,rcn_params(county,start,page_size))
            location = archive(response,"rcn")
            content = response.content
            manifest["pages"].append(location)
            manifest_file.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        records,total = rcn_page(content)
        if matched is not None and total != matched:
            raise ContractError("Liczba wyników WFS zmieniła się podczas importu; rozpocznij nowy import")
        matched = total
        for record in records:
            key = record["feature_id"]
            if key in seen:
                raise ContractError("WFS powtórzył obiekt pomiędzy stronami; nie można potwierdzić kompletności")
            seen.add(key)
        all_records.extend(records)
        start += len(records)
        log.info("import=%s pobrano=%s oczekiwane=%s",folder.name,start,matched)
        if not records or (matched is not None and start >= matched):
            if matched is not None and start != matched:
                raise ContractError("Liczba pobranych rekordów różni się od numberMatched")
            manifest["done"] = True
            manifest_file.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            break
    else:
        raise ContractError("Osiągnięto limit stron; import niekompletny")
    if not all_records:
        raise ContractError("Źródło nie zwróciło żadnej transakcji powiatu; nie usuwam dotychczasowych danych")
    report = save_batch(all_records,county)
    report["download_id"] = folder.name
    return report
