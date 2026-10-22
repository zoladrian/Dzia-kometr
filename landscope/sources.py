from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
import httpx
from .config import RCN_URL, ULDK_URL, data_dir
from .domain import ContractError, number, parcel_id, sale_date, land_category, stable_id
from .geometry import local, gml_geometry, uldk_wkt


class Unavailable(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def xml(content):
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ContractError("DTD/ENTITY niedozwolone")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ContractError("Odpowiedź nie jest poprawnym XML") from exc
    if local(root.tag) in {"ExceptionReport", "ServiceExceptionReport"}:
        raise ContractError("OGC: " + " ".join(root.itertext())[:500])
    return root


def fetch(url, params=None):
    timeout = float(os.getenv("LANDSCOPE_HTTP_TIMEOUT", "45"))
    last = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent":"LandScope/0.1 (local research)"}) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                break
            if attempt < 2:
                time.sleep(attempt+1)
    raise Unavailable(str(last))


def archive(response, source):
    content = response.content
    digest = hashlib.sha256(content).hexdigest()
    folder = data_dir() / "raw" / source
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (digest + ".bin")
    if not target.exists():
        target.write_bytes(content)
        target.with_suffix(".json").write_text(json.dumps({
            "source": source, "url":str(response.url), "fetched_at":utcnow(),
            "last_modified":response.headers.get("last-modified"), "etag":response.headers.get("etag"),
            "sha256":digest, "bytes":len(content)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


REQUIRED_RCN = {"tran_lokalny_id_iip", "tran_przestrzen_nazw", "dok_data", "dzi_id_dzialki", "dzi_pow_ewid"}
PRICE_FIELDS = {"tran_cena_brutto", "nier_cena_brutto", "dzi_cena_brutto"}


def rcn_schema(content):
    root = xml(content)
    if local(root.tag) != "schema":
        raise ContractError("DescribeFeatureType nie zwraca XSD")
    fields = set()
    for element in root.iter():
        if local(element.tag) != "element":
            continue
        name = element.get("name") or ""
        name = name.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
        if name:
            fields.add(name)
    missing = REQUIRED_RCN - fields
    if missing or not PRICE_FIELDS.intersection(fields):
        raise ContractError("Brak pól RCN: " + ", ".join(sorted(missing or PRICE_FIELDS)))
    return sorted(f for f in fields if f)


def normalize_rcn(fields, feature_id, geometry=None):
    for name in ("tran_lokalny_id_iip", "tran_przestrzen_nazw"):
        if not fields.get(name):
            raise ContractError("Brak trwałego identyfikatora transakcji: " + name)
    pid = parcel_id(fields.get("dzi_id_dzialki"))
    txid = stable_id(fields["tran_przestrzen_nazw"], fields["tran_lokalny_id_iip"])
    area = number(fields.get("dzi_pow_ewid"))
    price = number(fields.get("dzi_cena_brutto"))
    total = number(fields.get("tran_cena_brutto"))
    prop_price = number(fields.get("nier_cena_brutto"))
    prop_area = number(fields.get("nier_pow_gruntu"))
    issues = []
    if fields.get('_area_unit') == 'unavailable':
        area = prop_area = None
        issues.append('area_unit_unavailable')
    for name,value in (("area",area),("price",price),("total",total),("property_price",prop_price),("property_area",prop_area)):
        if value is not None and value <= 0:
            issues.append(name + "_nonpositive")
    date = sale_date(fields.get("dok_data"))
    if date is None:
        issues.append("date_missing")
    if area is None:
        issues.append("area_missing")
    if all(v is None for v in (price,total,prop_price)):
        issues.append("price_missing")
    if geometry is None:
        issues.append("geometry_missing")
    if not feature_id:
        raise ContractError("Brak identyfikatora obiektu źródłowego")
    return {
        "id":stable_id("rcn",feature_id), "feature_id":feature_id, "transaction_id":txid,
        "transaction_source_id":fields["tran_lokalny_id_iip"], "namespace":fields["tran_przestrzen_nazw"],
        "parcel_id":pid, "date":date, "price":str(price) if price is not None else None,
        "transaction_price":str(total) if total is not None else None,
        "property_price":str(prop_price) if prop_price is not None else None,
        "property_area":str(prop_area) if prop_area is not None else None,
        "area":str(area) if area is not None else None,
        "share":fields.get("nier_udzial"), "right":fields.get("nier_prawo"),
        "category":land_category(fields.get("nier_rodzaj")), "category_raw":fields.get("nier_rodzaj"),
        "land_use":fields.get("dzi_sposob_uzyt"), "address":fields.get("dzi_adres"),
        "plan_at_sale":fields.get("dzi_przezn_wmpzp"), "market":fields.get("tran_rodzaj_rynku"),
        "transaction_type":fields.get("tran_rodzaj_trans"), "source_version":fields.get("tran_wersja_id"),
        "geometry":geometry, "geometry_kind":"approximate_transaction" if geometry else "unavailable",
        "issues":issues,
        # Flat WFS has no stable property identity. This is a property observation,
        # never a claim that equal property attributes identify the same property.
        "property_identity":fields.get('_property_identity','unavailable'), "source":fields.get('_source',RCN_URL),
        "property_source_id":fields.get('_property_source_id'),
        "property_parcel_count":fields.get('_property_parcel_count'),
        "transaction_parcel_count":fields.get('_transaction_parcel_count'),
        "transaction_property_count":fields.get('_transaction_property_count'),
        "transaction_complete_land":fields.get('_transaction_complete_land',False),
        "transaction_area":fields.get('_transaction_area'),
        "transaction_full_share":fields.get('_transaction_full_share',False),
        "area_unit":"m2" if area is not None else None,
        "source_snapshot":fields.get('_source_snapshot'),
        "details":fields.get('_details') or {},
        "geometry_kind":"rcn_parcel_boundary" if geometry and fields.get('_property_identity')=='confirmed' else ('approximate_transaction' if geometry else 'unavailable'),
    }


def rcn_page(content):
    root = xml(content)
    if local(root.tag) != "FeatureCollection":
        raise ContractError("GetFeature nie zwraca FeatureCollection")
    features = []
    for member in root:
        if local(member.tag) not in {"member", "featureMember"}:
            continue
        for feature in member:
            if local(feature.tag) != "dzialki":
                raise ContractError("Nieoczekiwany typ obiektu RCN")
            fields = {local(e.tag).lower():"".join(e.itertext()).strip() or None for e in feature
                      if len(e)==0 or any(local(n.tag)=="timePosition" for n in e.iter())}
            fields['_area_unit'] = 'unavailable'  # Flat WFS does not declare uom.
            fid = feature.get("{http://www.opengis.net/gml/3.2}id") or feature.get("{http://www.opengis.net/gml}id") or feature.get("fid")
            geometry = None
            geometry_error = None
            try:
                geometry = gml_geometry(feature)
            except ContractError as exc:
                geometry_error = str(exc)
            features.append({"fields":fields,"feature_id":fid,"geometry":geometry,
                             "geometry_error":geometry_error,"raw_xml":ET.tostring(feature, encoding="unicode")})
    returned = root.get("numberReturned")
    if returned is not None and int(returned) != len(features):
        raise ContractError("numberReturned nie zgadza się z liczbą obiektów")
    matched = root.get("numberMatched")
    return features, int(matched) if matched and matched.isdigit() else None


def rcn_params(county, start=0, count=500):
    if not county.isdigit() or len(county) != 4:
        raise ContractError("Kod powiatu musi mieć 4 cyfry")
    return {"service":"WFS","version":"2.0.0","request":"GetFeature","typenames":"ms:dzialki",
            "count":count,"startIndex":start,"srsName":"urn:ogc:def:crs:EPSG::2180",
            "sortBy":"gid",
            "filter":'<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsLike wildCard="*" singleChar="?" escapeChar="!"><fes:ValueReference>DZI_ID_DZIALKI</fes:ValueReference><fes:Literal>'+county+'*</fes:Literal></fes:PropertyIsLike></fes:Filter>'}


ULDK_FIELDS = "id,commune,region,parcel,geom_wkt,datasource"


def parse_uldk(content, query=None, multiple=False):
    lines = [s.strip() for s in content.strip().splitlines() if s.strip()]
    if not lines:
        raise ContractError("Pusta odpowiedź ULDK")
    try:
        status = int(lines[0].split()[0])
    except (ValueError, IndexError) as exc:
        raise ContractError("Brak statusu ULDK") from exc
    if status < 0:
        raise Unavailable("ULDK: " + " ".join(lines)[:300])
    if multiple and status != len(lines)-1:
        raise ContractError("Niezgodna liczba wyników ULDK")
    result = []
    for line in lines[1:]:
        values = line.split("|")
        if len(values) < 6:
            raise ContractError("Niekompletna odpowiedź ULDK")
        pid,commune,region,nr,geometry,source = values[:6]
        parcel_id(pid)
        if query and pid != query:
            raise ContractError("ULDK zwrócił inną działkę")
        result.append({"id":pid,"commune":commune,"region":region,"number":nr,
                       "geometry":uldk_wkt(geometry),"source":ULDK_URL,"upstream_source":source,
                       "fetched_at":utcnow(),"geometry_kind":"parcel_boundary"})
    if not result:
        raise Unavailable("ULDK: brak wyników")
    return result


UUG_URL = "https://services.gugik.gov.pl/uug/"


def geocode_address(query):
    """GUGiK address points (PRG). Only exact house numbers; never a guessed street centre."""
    response = fetch(UUG_URL, {"request":"GetAddress","address":query,"srid":"4326"})
    archive(response,"uug")
    try:
        body = response.json()
    except ValueError as exc:
        raise ContractError("UUG nie zwrócił JSON") from exc
    results = body.get("results") or {}
    if not isinstance(results,dict) or not results:
        raise Unavailable("UUG: brak punktu adresowego dla: "+query[:120])
    found = []
    for item in results.values():
        if item.get("number") is None or str(item.get("accuracy")) not in {"1","1.0"}:
            continue
        lon,lat = float(item["x"]),float(item["y"])
        if not (13 <= lon <= 25 and 48 <= lat <= 56):
            raise ContractError("UUG: punkt poza Polską lub zła kolejność osi")
        label = ", ".join(filter(None,[item.get("city"),
                 " ".join(filter(None,[item.get("street"),item.get("number")])),item.get("code")]))
        found.append({"label":label,"lon":lon,"lat":lat,"teryt":item.get("teryt"),"simc":item.get("simc"),
                      "ulic":item.get("ulic"),"source":UUG_URL,"fetched_at":utcnow()})
    if not found:
        raise Unavailable("UUG: brak dokładnego punktu adresowego dla: "+query[:120])
    return found


def lookup_parcel(query=None, xy=None):
    if xy is not None:
        method = "GetParcelByXY"
        extra = {"xy":f"{xy[0]},{xy[1]},4326"}
    else:
        method = "GetParcelById" if query and __import__("re").fullmatch(r"\d{6}_.+", query) else "GetParcelByIdOrNr"
        extra = {"id":query}
    response = fetch(ULDK_URL, {"request":method, **extra, "result":ULDK_FIELDS, "srid":4326})
    archive(response,"uldk")
    return parse_uldk(response.text, query if method == "GetParcelById" else None, method == "GetParcelByIdOrNr")
