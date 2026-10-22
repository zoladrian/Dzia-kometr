"""Live checks. HTTP 200/capabilities alone NEVER mean usable parcel data."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from .config import RCN_URL, ULDK_URL
from .domain import ContractError, unit_price
from .sources import fetch, archive, xml, local, rcn_schema, rcn_page, rcn_params, normalize_rcn, lookup_parcel, Unavailable, utcnow

SOURCES = {
 "rcn": {"url":RCN_URL,"kind":"rcn","required":"trwałe ID transakcji i działki, data, cena z zakresem, powierzchnia, geometria/CRS"},
 "rcn_county": {"url":"https://api.dane.gov.pl/1.4/datasets/29243/resources","kind":"catalog","required":"plik GML powiatu, identyfikatory i relacje transakcja–nieruchomość–działka"},
 "uldk": {"url":ULDK_URL,"kind":"uldk","required":"zgodne ID, obręb/gmina, poprawny Polygon/MultiPolygon w EPSG:4326"},
 "uug": {"url":"https://services.gugik.gov.pl/uug/","kind":"uug","required":"dokładny punkt adresowy (PRG) w EPSG:4326 i działka ULDK pod nim"},
 "egib": {"url":"https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza","kind":"wfs","required":"ID działki i poprawna granica w jawnym CRS"},
 "mpzp": {"url":"https://mapy.geoportal.gov.pl/wss/ext/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego","kind":"wms","required":"przeznaczenie działki i odniesienie do obowiązującego planu"},
 "gesut": {"url":"https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaUzbrojeniaTerenu","kind":"wms","required":"typ sieci i geometria; bez deklaracji możliwości przyłączenia"},
 "gdos": {"url":"https://sdi.gdos.gov.pl/wfs","kind":"wfs","required":"geometria, nazwa i typ formy ochrony"},
 "isok": {"url":"https://isok.gov.pl/inspire.html","kind":"discovery","required":"warstwa zagrożenia powodziowego z prawdopodobieństwem i geometrią"},
 "bdot10k": {"url":"https://www.geoportal.gov.pl/pl/dane/baza-danych-obiektow-topograficznych-bdot10k/","kind":"discovery","required":"wektorowa geometria i typ drogi/obiektu"},
 "ortho": {"url":"https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution","kind":"wms","required":"obraz ortofoto i data wykonania dla wskazanego obszaru"},
 "nmt": {"url":"https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/","kind":"discovery","required":"wartości wysokości, układ pionowy i rozdzielczość"}
}


def check_source(name, sample_id=None):
    entry = SOURCES[name]
    result = {"source":name,"url":entry["url"],"checked_at":utcnow(),"status":"FAIL","required":entry["required"],"checks":{}}
    try:
        kind = entry["kind"]
        if kind == "rcn":
            response = fetch(entry["url"],{"service":"WFS","request":"DescribeFeatureType","version":"2.0.0","typenames":"ms:dzialki"})
            archive(response,name)
            result["checks"]["schema"] = rcn_schema(response.content)
            response = fetch(entry["url"],rcn_params("0801",count=30))
            result["archive"] = archive(response,name)
            rows,total = rcn_page(response.content)
            if not rows:
                raise Unavailable("Brak próbki powiatu gorzowskiego")
            normalized = [normalize_rcn(r["fields"],r["feature_id"],r["geometry"]) for r in rows]
            priced = [r for r in normalized if r["date"] and r["geometry"] and
                      any(r[k] is not None for k in ("price","transaction_price","property_price"))]
            result["checks"].update({"sample_count":len(rows),"number_matched":total,"with_date_price_geometry":len(priced),
                                    "with_area":sum(r["area"] is not None for r in normalized),
                                    "parcel_ids":[r["parcel_id"] for r in normalized[:5]],
                                    "explicit_unit_prices":sum(unit_price(r["price"],r["area"],scope="parcel",share=r["share"],category=r["category"]) is not None for r in normalized),
                                    "area_unit":"unavailable"})
            if not priced:
                raise ContractError("Próbka nie zawiera rekordu z datą, ceną i geometrią")
            if any(r["geometry_error"] for r in rows):
                raise ContractError("Niepoprawna geometria w próbce")
            result["status"],result["reason"] = "PASS","Kontrakt i próbka WFS poprawne. Jednostka powierzchni nie jest zadeklarowana, więc nie liczymy z niej ceny za m². Import powiatu używa GML z jawną jednostką."
        elif kind == "uldk":
            # "Kłodawa 1" is ambiguous in ULDK and currently returns other counties.
            # This id is from the deterministic Kłodawa sample of the 2026-10-14 county file.
            rows = lookup_parcel(sample_id or "080104_2.0002.1235/4")
            rows = [r for r in rows if r["id"].startswith("0801")]
            if not rows:
                raise Unavailable("Brak dopasowania do Kłodawy w powiecie 0801")
            if any(not r["commune"] or not r["region"] for r in rows):
                raise ContractError("ULDK nie zwrócił obrębu/gminy")
            result["checks"] = {"sample_count":len(rows),"parcel_ids":[r["id"] for r in rows],"crs":"EPSG:4326","geometry":"valid polygon"}
            result["status"],result["reason"] = "PASS","Zgodne identyfikatory i poprawne granice"
        elif kind == "uug":
            from .sources import geocode_address
            # A built-up address with a registered PRG point; plots sold as land often have no address point yet.
            points = geocode_address("Kłodawa, Gorzowska 40")
            parcels = lookup_parcel(xy=(points[0]["lon"],points[0]["lat"]))
            if not parcels[0]["id"].startswith("080104"):
                raise ContractError("Punkt adresowy Kłodawy nie trafia w działkę gminy Kłodawa")
            result["checks"] = {"address":points[0]["label"],"teryt":points[0]["teryt"],"parcel":parcels[0]["id"],"crs":"EPSG:4326"}
            result["status"],result["reason"] = "PASS","Dokładny punkt adresowy i działka ULDK pod nim"
        elif kind == "catalog":
            response = fetch(entry["url"])
            result["archive"] = archive(response,name)
            body = response.json()
            resources = body.get("data")
            if not isinstance(resources,list) or not resources:
                raise ContractError("Brak listy zasobów w katalogu")
            result["checks"]["resources"] = [{k:r.get("attributes",{}).get(k) for k in ("title","format","link","data_date","modified")} for r in resources]
            from .county import download_county, county_records
            content, metadata, path = download_county()
            rows, counts = county_records(content, metadata.get("data_date"))
            with_geometry = sum(1 for row in rows if row.get("geometry"))
            with_price = sum(1 for row in rows if any(row["fields"].get(name) for name in ("tran_cena_brutto","nier_cena_brutto","dzi_cena_brutto")))
            if not rows or not with_geometry or not with_price or "RCN_Transakcja" not in counts:
                raise ContractError("GML powiatu nie zawiera transakcji, cen i geometrii")
            result["archive"] = path
            result["checks"].update({"snapshot":metadata.get("data_date"),"download_url":metadata.get("link"),
                                     "source_objects":counts,"observations":len(rows),"with_geometry":with_geometry})
            result["status"],result["reason"] = "PASS","Pobrany GML powiatu ma relacje, identyfikatory, ceny i geometrię"
        elif kind in {"wms","wfs"}:
            response = fetch(entry["url"],{"SERVICE":kind.upper(),"REQUEST":"GetCapabilities"})
            result["archive"] = archive(response,name)
            root = xml(response.content)
            if local(root.tag) not in {"WMS_Capabilities","WMT_MS_Capabilities","WFS_Capabilities"}:
                raise ContractError("Nieprawidłowy dokument capabilities")
            names = [e.text for e in root.iter() if local(e.tag) == "Name" and e.text]
            result["checks"]["capabilities"] = "PASS"
            result["checks"]["layers"] = names[:100]
            # An unverified service is kept out of parcel facts. It cannot become
            # green merely because a generic image or layer list was returned.
            raise Unavailable("Capabilities poprawne; brak zweryfikowanego kontraktu danych wymaganych dla działki: "+entry["required"])
        else:
            response = fetch(entry["url"])
            archive(response,name)
            result["checks"]["documentation_reachable"] = True
            raise Unavailable("Osiągalna strona informacyjna; endpoint i kontrakt danych obszarowych niezweryfikowane")
    except Unavailable as exc:
        result["status"],result["reason"] = "UNAVAILABLE",str(exc)
    except (ContractError, ValueError, TypeError, KeyError) as exc:
        result["status"],result["reason"] = "FAIL",str(exc)
    except ImportError as exc:
        result["status"],result["reason"] = "UNAVAILABLE","Brak zależności: "+str(exc)
    return result


def diagnose(names=None, sample_id=None, output="reports/sources.json"):
    selected = names or list(SOURCES)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n:check_source(n,sample_id),selected))
    path = Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    return results
