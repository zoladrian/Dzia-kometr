import json
from collections import defaultdict
from decimal import Decimal
from .db import connect
from .domain import unit_price, money, distribution, evidence, ContractError, fold_text, FOLD_FROM, FOLD_TO, effective_unit_price, UNIT_BASIS
from . import card as cards
from .config import ULDK_URL


def where(filters):
    clauses,params = ["o.active"],[]
    bbox = filters.get("bbox")
    if bbox:
        clauses.append("ST_Intersects(COALESCE(p.boundary,o.location),ST_MakeEnvelope(%s,%s,%s,%s,4326))")
        params.extend(bbox)
    for key,sql in (
        ("date_from","s.sale_date >= %s"),("date_to","s.sale_date <= %s"),
        ("price_min","s.price >= %s"),("price_max","s.price <= %s"),
        ("area_min","o.area >= %s"),("area_max","o.area <= %s"),
        ("category","o.category = %s"),("parcel_id","o.parcel_id = %s"),
        ("county","o.county = %s"),
    ):
        if filters.get(key) is not None:
            clauses.append(sql)
            params.append(filters[key])
    if filters.get("place"):
        clauses.append("lower(translate(concat_ws(' ',o.address,p.commune,p.region,o.parcel_id),%s,%s)) LIKE %s ESCAPE '\\'")
        needle = fold_text(filters["place"]).replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
        params.extend([FOLD_FROM, FOLD_TO, "%"+needle+"%"])
    if filters.get("land_use"):
        clauses.append("o.land_use = %s")
        params.append(filters["land_use"])
    for key,sql in (("unit_min","o.unit_price >= %s"),("unit_max","o.unit_price <= %s")):
        if filters.get(key) is not None:
            clauses.append(sql + " AND o.unit_basis IN ('parcel_price','single_parcel_land_transaction')")
            params.append(filters[key])
    if filters.get("categories"):
        clauses.append("o.category = ANY(%s)")
        params.append(filters["categories"])
    if filters.get("counties"):
        clauses.append("o.county = ANY(%s)")
        params.append(filters["counties"])
    if filters.get("polygon"):
        clauses.append("ST_Intersects(COALESCE(p.boundary,o.location),ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))")
        params.append(json.dumps(filters["polygon"]))
    return " AND ".join(clauses),params


JOIN = " FROM observation o JOIN sale s ON s.id=o.sale_id JOIN parcel p ON p.id=o.parcel_id "


def public_observation(row):
    payload = row["payload"].copy()
    # Whitelist the normalized DTO; raw source fields never cross the public API.
    unit,basis = effective_unit_price(payload)
    payload["price_per_m2"] = money(unit)
    payload["price_per_m2_basis"] = basis
    payload["price_scope"] = "parcel" if payload["price"] is not None else None
    payload["price_per_m2_reason"] = UNIT_BASIS[basis] if basis else "Brak ceny działki, dodatniej powierzchni, pełnego udziału lub potwierdzonej kategorii"
    payload["fetched_at"] = str(row["fetched_at"])
    payload["evidence"] = {name:evidence(payload.get(name),payload["source"],payload.get("source_version"))
                           for name in ("date","price","transaction_price","area","share","land_use","plan_at_sale")}
    payload["evidence"]["price_per_m2"] = evidence(money(unit),payload["source"],status="inferred",note=payload["price_per_m2_reason"])
    payload["geometry"] = row.get("boundary") or payload.get("geometry")
    payload["geometry_kind"] = "parcel_boundary" if row.get("boundary") else payload["geometry_kind"]
    if row.get("boundary"):
        payload["geometry_source"] = ULDK_URL
    payload["commune"],payload["region"] = row.get("commune"),row.get("region")
    return payload


def transactions(filters, limit=50, offset=0, sort="date", order="desc"):
    clause,params = where(filters)
    column = {"date":"s.sale_date","price":"s.price","area":"sum(o.area)"}[sort]
    direction = {"asc":"ASC","desc":"DESC"}[order]
    with connect() as db:
        total = db.execute("SELECT count(DISTINCT s.id) AS n"+JOIN+"WHERE "+clause,params).fetchone()["n"]
        rows = db.execute("""SELECT s.id,s.sale_date,s.price,count(DISTINCT o.parcel_id) AS matching_parcels,
          array_agg(DISTINCT o.parcel_id) AS parcel_ids, sum(o.area) AS matching_area,
          min(o.category) AS category,
          (array_agg(o.payload->'details'->'parcel'->'address_parts'->0 ORDER BY o.parcel_id))[1] AS address,
          (array_agg(COALESCE(p.number,o.parcel_id) ORDER BY o.parcel_id))[1] AS number,
          (array_agg(p.region ORDER BY o.parcel_id))[1] AS region,
          max(o.unit_price) FILTER (WHERE o.unit_basis IN ('parcel_price','single_parcel_land_transaction')) AS unit_price,
          max(o.unit_price) FILTER (WHERE o.unit_basis='package_land_transaction') AS package_unit_price,
          max((o.payload->>'transaction_parcel_count')::int) AS parcels_in_act,
          ST_AsGeoJSON(ST_Centroid(ST_Collect(COALESCE(p.boundary,o.location))))::json AS geometry,
          ST_AsGeoJSON((array_agg(COALESCE(p.boundary,o.location) ORDER BY o.parcel_id))[1])::json AS focus_geometry"""
          +JOIN+"WHERE "+clause+f" GROUP BY s.id ORDER BY {column} {direction} NULLS LAST,s.id LIMIT %s OFFSET %s",[*params,limit,offset]).fetchall()
    for row in rows:
        row["price_scope"] = "transaction"
        row["geometry_kind"] = "approximate_transaction"
        row["area_scope"] = "suma powierzchni obserwacji pasujących do filtra; nie mianownik ceny transakcji"
        address = row.pop("address") or {}
        number = row.pop("number").rsplit(".",1)[-1]
        street = " ".join(filter(None,[cards.place_name(address.get("street")),address.get("number")]))
        row["title"] = street or f"Działka {number}"
        row["locality"] = cards.place_name(address.get("city")) or row.pop("region") or None
        row.pop("region",None)
    return {"items":rows,"total":total,"limit":limit,"offset":offset}


def bounds(filters):
    clause,params = where(filters)
    with connect() as db:
        row = db.execute("""SELECT ST_XMin(e) AS w,ST_YMin(e) AS s,ST_XMax(e) AS e,ST_YMax(e) AS n,count AS n_obs FROM (
          SELECT ST_Extent(COALESCE(p.boundary,o.location)) AS e,count(*) AS count"""+JOIN+"WHERE "+clause+") x",params).fetchone()
    return None if not row or row["w"] is None else {"bbox":[row["w"],row["s"],row["e"],row["n"]],"observations":row["n_obs"]}


def transaction_detail(identifier):
    with connect() as db:
        sale = db.execute("SELECT * FROM sale WHERE id=%s",(identifier,)).fetchone()
        if not sale:
            return None
        rows = db.execute("""SELECT o.payload,o.fetched_at,ST_AsGeoJSON(p.boundary)::json AS boundary,p.commune,p.region"""
                          +JOIN+"WHERE s.id=%s AND o.active ORDER BY o.parcel_id",(identifier,)).fetchall()
        sale["observations"] = [public_observation(r) for r in rows]
        sale["parcel_ids"] = sorted({r["parcel_id"] for r in sale["observations"]})
        sale["price_scope"] = "transaction"
        identities = {item.get("property_identity") for item in sale["observations"]}
        sale["property_identity"] = "confirmed" if identities == {"confirmed"} else "unavailable"
        if sale["property_identity"] == "confirmed" and sale["observations"] and all(item.get("transaction_complete_land") for item in sale["observations"]):
            sale["completeness_note"] = "Relacje pochodzą z GML powiatowego. Plik obejmuje cały grunt tej transakcji. Cena aktu nie jest ceną pojedynczej działki."
        elif sale["property_identity"] == "confirmed":
            sale["completeness_note"] = "Relacje pochodzą z GML powiatowego. Zakres aktu nie jest wyłącznie kompletnym gruntem. Cena aktu nie jest ceną pojedynczej działki."
        else:
            sale["completeness_note"] = "Działki znalezione w warstwie RCN; brak gwarancji pełnego zakresu aktu. Nie dzielimy ceny aktu przez ich powierzchnię."
        return sale


SINGLE_BASES = "('parcel_price','single_parcel_land_transaction')"
SCALE_LABEL = {"unbuilt":"Niezabudowane","built":"Zabudowane","unknown":"Lokale i inne"}


def comparable_category(filters):
    """Heat scale uses one category so built and unbuilt zł/m² are never one median."""
    if filters.get("category"):
        return filters["category"]
    cats = filters.get("categories") or []
    if len(cats) == 1:
        return cats[0]
    return "unbuilt"


def scale_filters(filters):
    out = {k:v for k,v in filters.items() if k not in ("bbox","polygon","category","categories")}
    out["category"] = comparable_category(filters)
    return out


def price_scale(db, clause, params):
    row = db.execute("""SELECT percentile_cont(0.05) WITHIN GROUP (ORDER BY o.unit_price) AS low,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY o.unit_price) AS median,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY o.unit_price) AS high,count(*) AS n"""
        +JOIN+"WHERE "+clause+" AND o.unit_basis IN "+SINGLE_BASES+
        " AND (SELECT count(DISTINCT x.parcel_id) FROM observation x WHERE x.sale_id=o.sale_id AND x.active)=1",params).fetchone()
    if not row or not row["n"]:
        return {"min":None,"median":None,"max":None,"count":0}
    return {"min":money(Decimal(str(row["low"]))),"median":money(Decimal(str(row["median"]))),
            "max":money(Decimal(str(row["high"]))),"count":row["n"]}


def _favorite_features(db, filters):
    geom = """COALESCE(p.boundary,(SELECT o.location FROM observation o WHERE o.parcel_id=p.id AND o.location IS NOT NULL LIMIT 1))"""
    clauses,params = [],[]
    bbox = filters.get("bbox")
    if bbox:
        clauses.append("ST_Intersects("+geom+",ST_MakeEnvelope(%s,%s,%s,%s,4326))")
        params.extend(bbox)
    if filters.get("polygon"):
        clauses.append("ST_Intersects("+geom+",ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))")
        params.append(json.dumps(filters["polygon"]))
    where_sql = (" WHERE "+" AND ".join(clauses)) if clauses else ""
    saved = db.execute("""SELECT p.id,p.number,f.label,ST_AsGeoJSON(ST_PointOnSurface("""+geom+"""))::json AS geometry
        FROM favorite f JOIN parcel p ON p.id=f.parcel_id"""+where_sql,params).fetchall()
    return [{"type":"Feature","geometry":r["geometry"],"properties":{"parcel_id":r["id"],"number":r["number"] or r["id"].rsplit(".",1)[-1],
             "label":r["label"],"favorite":True,"geometry_kind":"favorite_point","sales":None}} for r in saved if r["geometry"]]


def map_features(filters, zoom):
    """Clusters when zoomed out, one coloured point per parcel in the middle range, outlines with labels close up."""
    clause,params = where(filters)
    mode = "clusters" if zoom < 11 else ("points" if zoom < 15 else "parcels")
    heat = comparable_category(filters)
    with connect() as db:
        # Colour scale over the county for one comparable category, so a parcel keeps its colour while panning.
        scale = price_scale(db,*where(scale_filters(filters)))
        scale["view_median"] = price_scale(db,*where({**scale_filters(filters),"bbox":filters.get("bbox"),"polygon":filters.get("polygon")}))["median"]
        scale["category"] = heat
        scale["label"] = SCALE_LABEL[heat]
        favorites = _favorite_features(db, filters)
        if mode == "clusters":
            size = 360 / (2**zoom) / 4
            rows = db.execute("""WITH points AS (
                SELECT s.id,ST_Centroid(ST_Collect(COALESCE(p.boundary,o.location))) AS geom,
                max(o.unit_price) FILTER (WHERE o.unit_basis IN """+SINGLE_BASES+""" AND o.category=%s
                  AND (SELECT count(DISTINCT x.parcel_id) FROM observation x WHERE x.sale_id=o.sale_id AND x.active)=1) AS unit"""
                +JOIN+"WHERE "+clause+""" GROUP BY s.id)
                SELECT floor(ST_X(geom)/%s) AS gx,floor(ST_Y(geom)/%s) AS gy,count(*) AS count,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY unit) AS median,
                ST_AsGeoJSON(ST_Centroid(ST_Collect(geom)))::json AS geometry FROM points
                WHERE geom IS NOT NULL GROUP BY gx,gy""",[heat,*params,size,size]).fetchall()
            features = [{"type":"Feature","geometry":r["geometry"],"properties":{"count":r["count"],"geometry_kind":"cluster",
                         "median_price_per_m2":money(Decimal(str(r["median"]))) if r["median"] is not None else None}} for r in rows]
            return {"type":"FeatureCollection","mode":mode,"aggregated":True,"scale":scale,"features":features+favorites}
        geometry_sql = "ST_PointOnSurface(COALESCE(p.boundary,o.location))" if mode == "points" else "COALESCE(p.boundary,o.location)"
        limit = 6000 if mode == "points" else 2000
        # One feature per parcel: its newest matching sale, plus the number of matching sales.
        rows = db.execute("""SELECT * FROM (SELECT DISTINCT ON (o.parcel_id) o.parcel_id,o.sale_id,s.sale_date,s.price AS transaction_price,
            o.unit_price,o.unit_basis,o.category,o.area,p.number,f.label,f.parcel_id IS NOT NULL AS favorite,
            count(*) OVER (PARTITION BY o.parcel_id) AS sales,
            ST_AsGeoJSON("""+geometry_sql+""")::json AS geometry,
            CASE WHEN p.boundary IS NOT NULL THEN 'parcel_boundary'
                 WHEN o.payload->>'geometry_kind' = 'rcn_parcel_boundary' THEN 'rcn_parcel_boundary'
                 ELSE 'approximate_transaction' END AS geometry_kind"""
            +JOIN+" LEFT JOIN favorite f ON f.parcel_id=o.parcel_id WHERE "+clause+
            f" ORDER BY o.parcel_id,s.sale_date DESC NULLS LAST) x ORDER BY favorite DESC,parcel_id LIMIT {limit+1}",params).fetchall()
        bbox = filters.get("bbox")
        extra = []
        if mode == "parcels" and (bbox or filters.get("polygon")):
            extra_sql, extra_params = ["p.boundary IS NOT NULL",
                "NOT EXISTS (SELECT 1 FROM observation o WHERE o.parcel_id=p.id AND o.active)"], []
            if bbox:
                extra_sql.append("ST_Intersects(p.boundary,ST_MakeEnvelope(%s,%s,%s,%s,4326))")
                extra_params.extend(bbox)
            if filters.get("polygon"):
                extra_sql.append("ST_Intersects(p.boundary,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))")
                extra_params.append(json.dumps(filters["polygon"]))
            extra = db.execute("""SELECT p.id AS parcel_id,p.number,f.label,f.parcel_id IS NOT NULL AS favorite,
                ST_AsGeoJSON(p.boundary)::json AS geometry FROM parcel p LEFT JOIN favorite f ON f.parcel_id=p.id
                WHERE """+" AND ".join(extra_sql)+" LIMIT 500", extra_params).fetchall()
    features = []
    for r in rows[:limit]:
        comparable = r["unit_basis"] in ("parcel_price","single_parcel_land_transaction")
        props = {"parcel_id":r["parcel_id"],"number":r["number"] or r["parcel_id"].rsplit(".",1)[-1],"sale_id":r["sale_id"],
                 "sale_date":r["sale_date"],"transaction_price":r["transaction_price"],"sales":r["sales"],
                 "category":r["category"],"area":r["area"],
                 "price_per_m2":money(r["unit_price"]) if comparable else None,
                 "price_per_m2_basis":r["unit_basis"] if comparable else None,
                 "geometry_kind":r["geometry_kind"] if mode == "parcels" else "parcel_point",
                 "favorite":r["favorite"],"label":r["label"]}
        if r["geometry"]:
            features.append({"type":"Feature","geometry":r["geometry"],"properties":props})
    for r in extra:
        features.append({"type":"Feature","geometry":r["geometry"],"properties":{
            "parcel_id":r["parcel_id"],"number":r["number"] or r["parcel_id"].rsplit(".",1)[-1],"sale_id":None,"sales":0,
            "geometry_kind":"parcel_boundary","favorite":r["favorite"],"label":r["label"]}})
    if mode == "points":
        features += [f for f in favorites if not any(x["properties"]["parcel_id"] == f["properties"]["parcel_id"] for x in features)]
    return {"type":"FeatureCollection","mode":mode,"aggregated":False,"truncated":len(rows)>limit,"scale":scale,"features":features}


def statistics(filters):
    clause,params = where(filters)
    with connect() as db:
        rows = db.execute("""SELECT o.payload,s.sale_date,
          (SELECT count(DISTINCT x.parcel_id) FROM observation x WHERE x.sale_id=o.sale_id AND x.active) AS parcel_count,
          (SELECT count(*) FROM observation x WHERE x.sale_id=o.sale_id AND x.active) AS observation_count"""
          +JOIN+"WHERE "+clause+" ORDER BY o.id LIMIT 50001",params).fetchall()
    if len(rows)>50000:
        raise ContractError("Obszar ma ponad 50000 obserwacji; zawęź filtry statystyk")
    groups = defaultdict(lambda:{"observations":0,"values":[],"excluded":0})
    for row in rows:
        item = row["payload"]
        package = row["parcel_count"]>1 or row["observation_count"]>1
        year = str(row["sale_date"].year) if row["sale_date"] else "unknown"
        value,basis = effective_unit_price(item)
        # Packages are counted in their own group but never enter a median.
        if package or basis == "package_land_transaction":
            value = None
        key = (item["category"],"package" if package else "single",item["market"] or "unknown",item["right"] or "unknown",year)
        group = groups[key]
        group["observations"] += 1
        group.setdefault("bases",set())
        if value is None:
            group["excluded"] += 1
        else:
            group["values"].append(value)
            group["bases"].add(basis)
    return {"groups":[{"category":k[0],"scope":k[1],"market":k[2],"right":k[3],"year":k[4],
             "observations":v["observations"],"excluded":v["excluded"],"bases":sorted(v.get("bases",())),
             **distribution(v["values"])} for k,v in sorted(groups.items(),key=lambda kv:(kv[0][4],kv[0]),reverse=True)],
             "note":"Nominalne ceny brutto za ar, pełny udział, tylko jedna działka w akcie: cena działki z RCN albo cena aktu obejmującego wyłącznie tę działkę gruntu. Pakiety, lokale i budynki poza medianą. Osobno: rok, kategoria, rynek i prawo."}


def save_parcel(item):
    from psycopg.types.json import Jsonb
    with connect() as db:
        db.execute("""INSERT INTO parcel(id,commune,region,number,boundary,geometry_source,geometry_fetched_at,upstream_source)
          VALUES (%s,%s,%s,%s,ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)),%s,%s,%s)
          ON CONFLICT(id) DO UPDATE SET commune=excluded.commune,region=excluded.region,number=excluded.number,
          boundary=excluded.boundary,geometry_source=excluded.geometry_source,geometry_fetched_at=excluded.geometry_fetched_at,upstream_source=excluded.upstream_source""",
          (item["id"],item["commune"],item["region"],item["number"],json.dumps(item["geometry"]),item["source"],item["fetched_at"],item["upstream_source"]))
        db.execute("""INSERT INTO enrichment(parcel_id,source,payload) VALUES (%s,'uldk',%s)
          ON CONFLICT(parcel_id,source) DO UPDATE SET payload=excluded.payload,fetched_at=now()""",(item["id"],Jsonb(item)))


def parcel_detail(identifier):
    with connect() as db:
        row = db.execute("""SELECT id,commune,region,number,ST_AsGeoJSON(boundary)::json AS geometry,
          geometry_source,geometry_fetched_at,upstream_source FROM parcel WHERE id=%s""",(identifier,)).fetchone()
        if not row:
            return None
        sales = db.execute("""SELECT DISTINCT s.id,s.sale_date,s.price FROM sale s JOIN observation o ON o.sale_id=s.id
          WHERE o.parcel_id=%s AND o.active ORDER BY s.sale_date DESC NULLS LAST,s.id""",(identifier,)).fetchall()
        row["sales"] = sales
        row["favorite"] = db.execute("SELECT label FROM favorite WHERE parcel_id=%s",(identifier,)).fetchone()
        row["enrichments"] = db.execute("SELECT source,payload,fetched_at FROM enrichment WHERE parcel_id=%s",(identifier,)).fetchall()
        row["geometry_kind"] = "parcel_boundary" if row["geometry"] else "unavailable"
        row["history_note"] = "Brak transakcji w bazie nie oznacza, że działka nigdy nie była sprzedana."
        row["context"] = {key:evidence(None,None,note="Brak zweryfikowanej informacji dla działki")
                          for key in ("current_plan","utilities","flood_risk","nature_protection")}
        return row


def _latest_import(db):
    run = db.execute("""SELECT report,finished_at FROM import_run WHERE status='complete' ORDER BY finished_at DESC LIMIT 1""").fetchone()
    return {**run["report"],"finished_at":run["finished_at"]} if run else None


def _sale_cards(db, parcel_filter, params):
    rows = db.execute("""SELECT o.payload,o.parcel_id,s.id AS sale_id,s.sale_date,s.price FROM observation o JOIN sale s ON s.id=o.sale_id
      WHERE o.active AND """+parcel_filter+" ORDER BY s.sale_date DESC NULLS LAST,s.id,o.parcel_id",params).fetchall()
    result = []
    for i,r in enumerate(rows):
        sale = {"sale_date":r["sale_date"],"price":r["price"]}
        title = f"{r['sale_date'] or 'Brak daty'} · {cards.money(r['price']) or 'cena niedostępna'} — cały akt"
        result.append({"id":r["sale_id"],"parcel_id":r["parcel_id"],"title":title,
                       "sections":cards.observation_sections(f"sale.{i}",r["payload"],sale,"RCN")})
    return rows,result


def parcel_card(identifier):
    with connect() as db:
        parcel = db.execute("""SELECT id,commune,region,number,ST_AsGeoJSON(boundary)::json AS geometry,
          geometry_source,geometry_fetched_at,upstream_source,ST_Area(boundary::geography) AS boundary_area,
          ARRAY[ST_X(ST_PointOnSurface(boundary)),ST_Y(ST_PointOnSurface(boundary))] AS boundary_center
          FROM parcel WHERE id=%s""",(identifier,)).fetchone()
        if not parcel:
            return None
        rcn = db.execute("""SELECT ST_AsGeoJSON(o.location)::json AS geometry,ST_Area(o.location::geography) AS area,
          ARRAY[ST_X(ST_PointOnSurface(o.location)),ST_Y(ST_PointOnSurface(o.location))] AS center
          FROM observation o JOIN sale s ON s.id=o.sale_id WHERE o.parcel_id=%s AND o.active AND o.location IS NOT NULL
          ORDER BY s.sale_date DESC NULLS LAST LIMIT 1""",(identifier,)).fetchone()
        rows,sales = _sale_cards(db,"o.parcel_id=%s",(identifier,))
        precinct = identifier.rsplit(".",1)[0]
        trend = db.execute("""SELECT extract(year FROM s.sale_date)::int AS year,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY o.unit_price) AS median,count(*) AS n
          FROM observation o JOIN sale s ON s.id=o.sale_id WHERE o.active AND o.parcel_id LIKE %s AND o.category='unbuilt'
          AND o.unit_basis IN """+SINGLE_BASES+""" AND s.sale_date IS NOT NULL
          GROUP BY 1 ORDER BY 1 DESC LIMIT 10""",(precinct.replace("_","\\_")+".%",)).fetchall()
        address = db.execute("SELECT payload FROM enrichment WHERE parcel_id=%s AND source='uug'",(identifier,)).fetchone()
        favorite = db.execute("SELECT label FROM favorite WHERE parcel_id=%s",(identifier,)).fetchone()
        imported = _latest_import(db)
    parcel["rcn_geometry"] = rcn and rcn["geometry"]
    if parcel["geometry"]:
        parcel["geometry_area"],parcel["center"] = parcel["boundary_area"],parcel["boundary_center"]
    elif rcn:
        parcel["geometry_area"],parcel["center"] = rcn["area"],rcn["center"]
    latest = rows[0]["payload"] if rows else None
    unique_sales = list({r["sale_id"]:r for r in rows}.values())
    sections = cards.summary_sections(rows,trend,parcel["region"] or precinct.split(".")[-1]) + cards.parcel_sections(
        parcel,latest,unique_sales,address and address["payload"],favorite and (favorite["label"] or "Zapisana bez etykiety"),imported)
    number = parcel["number"] or identifier.rsplit(".",1)[-1]
    parts = ((latest or {}).get("details") or {}).get("parcel",{}).get("address_parts") or [{}]
    street = " ".join(filter(None,[cards.place_name(parts[0].get("street")),parts[0].get("number")]))
    place = ", ".join(filter(None,[street or None,cards.place_name(parts[0].get("city")) or parcel["commune"]]))
    if address:
        place = address["payload"]["label"]
    owner = cards.party(latest)[1]
    return {"id":identifier,"number":number,
            "title":(favorite and favorite["label"]) or (street and f"{street} · dz. {number}") or f"Działka {number}",
            "subtitle":" · ".join(filter(None,[place or None,f"obręb {parcel['region']}" if parcel["region"] else None,
                                              f"właściciel: {owner}" if owner else None])),
            "favorite":favorite is not None,"geometry":parcel["geometry"] or parcel["rcn_geometry"],
            "geometry_kind":"parcel_boundary" if parcel["geometry"] else ("rcn_parcel_boundary" if parcel["rcn_geometry"] else "unavailable"),
            "sections":sections,"sales":sales}


def transaction_card(identifier):
    with connect() as db:
        sale = db.execute("SELECT id,sale_date,price FROM sale WHERE id=%s",(identifier,)).fetchone()
        if not sale:
            return None
        rows,observations = _sale_cards(db,"s.id=%s",(identifier,))
        geo = db.execute("""SELECT ST_AsGeoJSON(ST_Collect(geom))::json AS g,
          ST_AsGeoJSON((array_agg(geom ORDER BY parcel_id))[1])::json AS focus
          FROM (SELECT o.parcel_id, COALESCE(p.boundary,o.location) AS geom FROM observation o
            JOIN parcel p ON p.id=o.parcel_id WHERE o.sale_id=%s AND o.active) x""",(identifier,)).fetchone()
    for item in observations:
        item["title"] = f"Działka {item['parcel_id']}"
    count = len({r["parcel_id"] for r in rows})
    return {"id":identifier,"title":f"Transakcja {sale['sale_date'] or ''} · {cards.money(sale['price']) or 'cena niedostępna'}",
            "subtitle":f"Akt obejmuje {count} " + ("działkę" if count == 1 else "działki" if count % 10 in (2,3,4) and count % 100 not in (12,13,14) else "działek"),
            "parcel_ids":sorted({r["parcel_id"] for r in rows}),"geometry":geo["g"],"focus_geometry":geo["focus"],
            "sections":[],"sales":observations}


def parcels_for_address(query):
    from .sources import geocode_address, lookup_parcel
    result = []
    for point in geocode_address(query)[:5]:
        for item in lookup_parcel(xy=(point["lon"],point["lat"])):
            save_parcel(item)
            save_address(item["id"],point)
            result.append({"id":item["id"],"commune":item["commune"],"region":item["region"],"number":item["number"],
                           "address":point["label"],"geometry":item["geometry"]})
    return result


def save_address(parcel_id, address):
    from psycopg.types.json import Jsonb
    with connect() as db:
        db.execute("""INSERT INTO enrichment(parcel_id,source,payload) VALUES (%s,'uug',%s)
          ON CONFLICT(parcel_id,source) DO UPDATE SET payload=excluded.payload,fetched_at=now()""",(parcel_id,Jsonb(address)))


def search_local(query, commune=None):
    with connect() as db:
        return db.execute("""SELECT id,commune,region,number,ST_AsGeoJSON(boundary)::json AS geometry FROM parcel
          WHERE (id=%s OR (number=%s AND (%s::text IS NULL OR commune ILIKE %s)))
          ORDER BY id LIMIT 100""",(query,query,commune,commune)).fetchall()


def favorites():
    with connect() as db:
        return db.execute("""SELECT f.parcel_id,f.label,p.commune,p.region FROM favorite f
          JOIN parcel p ON p.id=f.parcel_id ORDER BY f.created_at DESC""").fetchall()


def set_favorite(identifier,label=None):
    with connect() as db:
        if label is None:
            db.execute("DELETE FROM favorite WHERE parcel_id=%s",(identifier,))
        else:
            db.execute("INSERT INTO favorite(parcel_id,label) VALUES (%s,%s) ON CONFLICT(parcel_id) DO UPDATE SET label=excluded.label",(identifier,label))


def quality_report():
    with connect() as db:
        return {
            "active_observations":db.execute("SELECT count(*) n FROM observation WHERE active").fetchone()["n"],
            "missing_location":db.execute("SELECT count(*) n FROM observation o JOIN parcel p ON p.id=o.parcel_id WHERE o.active AND o.location IS NULL AND p.boundary IS NULL").fetchone()["n"],
            "issues":db.execute("SELECT issue,count(*) n FROM observation o CROSS JOIN LATERAL jsonb_array_elements_text(o.payload->'issues') issue WHERE active GROUP BY issue").fetchall(),
            "rejected":db.execute("SELECT reason,count(*) n FROM rejected_record GROUP BY reason").fetchall(),
            "imports":db.execute("SELECT * FROM import_run ORDER BY started_at DESC LIMIT 10").fetchall()
        }
