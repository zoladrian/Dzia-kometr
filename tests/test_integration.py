import copy
import pytest
from fastapi.testclient import TestClient
from landscope.importer import save_batch
from landscope import repository as repo
from landscope.api import create_app
from landscope.domain import ContractError

pytestmark=[pytest.mark.integration,pytest.mark.regression]


def test_import_idempotency_versions_and_raw(database,raw):
    first=save_batch([raw,copy.deepcopy(raw)],"0801")
    assert first["accepted"]==1 and first["duplicates"]==1
    counts=database.counts()
    save_batch([raw],"0801")
    after=database.counts()
    for name in ("sale","parcel","observation","property","raw_record"):
        assert after[name]==counts[name]
    changed=copy.deepcopy(raw);changed["fields"]["dzi_cena_brutto"]="210000"
    changed["fields"]["tran_wersja_id"]="2025-02-01T00:00:00"
    save_batch([changed],"0801")
    assert database.counts()["raw_record"]==2
    with database.connect() as c:
        row=c.execute("SELECT price FROM observation").fetchone()
        assert str(row["price"])=="210000"
        evidence=c.execute("SELECT payload FROM raw_record ORDER BY id DESC").fetchone()["payload"]
        assert evidence==changed
    with pytest.raises(ContractError): save_batch([raw],"0801")


@pytest.mark.quality
def test_packages_never_allocate_total(database,raw):
    second=copy.deepcopy(raw);second["feature_id"]="dzialki.TEST-2"
    second["fields"]["dzi_id_dzialki"]="080104_2.0001.124"
    raw["fields"]["dzi_cena_brutto"]=None;second["fields"]["dzi_cena_brutto"]=None
    save_batch([raw,second],"0801")
    result=repo.transactions({"bbox":[15,52,16,53]})
    assert result["total"]==1
    detail=repo.transaction_detail(result["items"][0]["id"])
    assert len(detail["parcel_ids"])==2
    assert all(o["price_per_m2"] is None for o in detail["observations"])
    assert all(g["scope"]=="package" and g["count"]==0 for g in repo.statistics({})["groups"])


def test_bad_record_quarantine_and_atomic_rollback(database,raw):
    broken=copy.deepcopy(raw);broken["feature_id"]="bad";broken["fields"]["dzi_id_dzialki"]="INVALID"
    result=save_batch([raw,broken],"0801")
    assert result["rejected"]==1 and not result["complete"]
    assert database.counts()["observation"]==1
    conflict=copy.deepcopy(raw);conflict["feature_id"]="conflict";conflict["fields"]["tran_cena_brutto"]="1"
    with pytest.raises(ContractError): save_batch([raw,conflict],"0801")
    assert database.counts()["observation"]==1
    # Retrying the batch after the interrupted/failed transaction is safe.
    save_batch([raw],"0801")
    assert database.counts()["observation"]==1


def test_api_filters_bbox_pagination_detail_statistics(database,raw):
    save_batch([raw],"0801")
    with TestClient(create_app(initialize=False)) as client:
        base="/api/transactions?bbox=15,52,16,53"
        data=client.get(base).json()
        assert data["total"]==1
        for suffix in ("&price_min=600000","&date_from=2025-01-01","&area_max=999","&category=built","&place=NoSuchPlace"):
            assert client.get(base+suffix).json()["total"]==0
        assert client.get(base+"&offset=1").json()["items"]==[]
        assert client.get("/api/transactions?bbox=17,52,18,53").json()["total"]==0
        detail=client.get("/api/transactions/"+data["items"][0]["id"]).json()
        assert detail["observations"][0]["price_per_m2"]=="200.00"
        assert client.get("/api/transactions/missing").status_code==404
        assert client.get("/api/map?bbox=15,52,16,53&zoom=10").json()["features"][0]["properties"]["count"]==1
        stats=client.get("/api/statistics?bbox=15,52,16,53").json()
        assert stats["groups"][0]["median"]=="200.00"


def test_card_endpoints_and_map_labels(database,raw):
    save_batch([raw],"0801")
    with TestClient(create_app(initialize=False)) as client:
        pid=raw["fields"]["dzi_id_dzialki"]
        card=client.get("/api/parcel/card",params={"id":pid}).json()
        rows={r["key"]:r for s in card["sections"] for r in s["rows"]}
        assert rows["parcel.id"]["value"]==pid and rows["history.count"]["value"]=="1"
        sale_rows={r["key"]:r for s in card["sales"][0]["sections"] for r in s["rows"]}
        assert sale_rows["sale.0.transaction.price"]["value"]=="500 000,00 zł"
        assert sale_rows["sale.0.parcel.unit_price"]["value"]=="20 000,00 zł/ar"
        assert client.get("/api/parcel/card",params={"id":"080104_2.0002.999"}).status_code==404
        tx=client.get(f"/api/transactions/{card['sales'][0]['id']}/card").json()
        assert tx["parcel_ids"]==[pid]
        assert client.get("/api/transactions/missing/card").status_code==404
        assert client.get("/api/address",params={"q":"a"}).status_code==422
        client.put("/api/favorite",params={"id":pid},json={"label":"Testowa"})
        feature=client.get("/api/map?bbox=15,52,16,53&zoom=17").json()["features"][0]["properties"]
        assert feature["parcel_id"]==pid and feature["number"]=="123/4" and feature["favorite"] and feature["label"]=="Testowa"
        clusters=client.get("/api/map?bbox=15,52,16,53&zoom=10").json()["features"]
        assert any(f["properties"].get("geometry_kind")=="favorite_point" for f in clusters)
        points=client.get("/api/map?bbox=15,52,16,53&zoom=13").json()
        assert points["mode"]=="points" and points["scale"]["median"]=="200.00"
        assert points["scale"]["category"]=="unbuilt"
        outside=client.get("/api/map?bbox=20,50,21,51&zoom=10").json()["features"]
        assert not any(f["properties"].get("geometry_kind")=="favorite_point" for f in outside)
        item=client.get("/api/transactions?bbox=15,52,16,53").json()["items"][0]
        assert item["title"] and str(item["unit_price"]).startswith("200")
        for query,expected in (("&unit_min=150",1),("&unit_min=300",0),("&unit_max=100",0),("&categories=unbuilt",1),("&categories=built",0),("&counties=0801",1),("&counties=1412",0)):
            assert client.get("/api/transactions?bbox=15,52,16,53"+query).json()["total"]==expected,query
        assert client.get("/api/transactions?bbox=15,52,16,53&categories=bad").status_code==422
        assert client.get("/api/bounds",params={"place":"Kłodawa"}).json()["observations"]==1
        assert client.get("/api/bounds",params={"place":"NoSuchPlace"}).status_code==404
        counties=client.get("/api/counties").json()
        assert counties["items"][0]["code"]=="0801" and counties["items"][1]["code"]=="1412"
        assert "Arynów" in counties["items"][1]["hint"]
        assert client.put("/api/counties",json={"selected":["0801","1412"]}).json()["selected"]==["0801","1412"]
        assert client.put("/api/counties",json={"selected":["9999"]}).status_code==422


def test_parcel_favorite_and_search_slash(database,raw):
    save_batch([raw],"0801")
    with TestClient(create_app(initialize=False)) as client:
        pid=raw["fields"]["dzi_id_dzialki"]
        assert client.get("/api/parcel",params={"id":pid}).status_code==200
        assert client.get("/api/parcels/search",params={"q":pid,"online":False}).json()["items"][0]["id"]==pid
        assert client.put("/api/favorite",params={"id":pid},json={"label":"Moja działka"}).status_code==200
        assert len(client.get("/api/favorites").json())==1
        client.delete("/api/favorite",params={"id":pid})
        assert client.get("/api/favorites").json()==[]


def test_map_scale_keeps_unbuilt_when_categories_mix(database,raw):
    built=copy.deepcopy(raw)
    built["feature_id"]="dzialki.TEST-B"
    built["fields"]["dzi_id_dzialki"]="080104_2.0001.200"
    built["fields"]["tran_lokalny_id_iip"]="TEST-T2"
    built["fields"]["nier_rodzaj"]="grunt zabudowany"
    built["fields"]["dzi_cena_brutto"]="900000.00"
    save_batch([raw,built],"0801")
    with TestClient(create_app(initialize=False)) as client:
        mixed=client.get("/api/map?bbox=15,52,16,53&zoom=13").json()["scale"]
        land=client.get("/api/map?bbox=15,52,16,53&zoom=13&categories=unbuilt").json()["scale"]
        house=client.get("/api/map?bbox=15,52,16,53&zoom=13&categories=built").json()["scale"]
        assert mixed["category"]=="unbuilt" and mixed["median"]==land["median"]=="200.00"
        assert house["category"]=="built" and house["median"]=="900.00"


def test_map_scale_excludes_multi_parcel_acts(database,raw):
    other=copy.deepcopy(raw)
    other["feature_id"]="dzialki.TEST-2"
    other["fields"]["dzi_id_dzialki"]="080104_2.0001.124"
    save_batch([raw,other],"0801")
    with TestClient(create_app(initialize=False)) as client:
        scale=client.get("/api/map?bbox=15,52,16,53&zoom=13").json()["scale"]
        assert scale["category"]=="unbuilt" and scale["count"]==0 and scale["median"] is None


def test_confirmed_gml_property_is_one_row_for_two_parcels(database,raw):
    second=copy.deepcopy(raw)
    second["feature_id"]="dzialki.TEST-2"
    second["fields"]["dzi_id_dzialki"]="080104_2.0001.124"
    for item in (raw,second):
        item["fields"]["_property_identity"]="confirmed"
        item["fields"]["_property_source_id"]="RCN_N_1"
    save_batch([raw,second],"0801")
    with database.connect() as db:
        props=db.execute("SELECT id FROM property").fetchall()
        obs=db.execute("SELECT property_id FROM observation").fetchall()
    assert len(props)==1 and len(obs)==2 and {r["property_id"] for r in obs}=={props[0]["id"]}


def test_initialize_merges_legacy_confirmed_property_copies(database,raw):
    second=copy.deepcopy(raw)
    second["feature_id"]="dzialki.TEST-2"
    second["fields"]["dzi_id_dzialki"]="080104_2.0001.124"
    for item in (raw,second):
        item["fields"]["_property_identity"]="confirmed"
        item["fields"]["_property_source_id"]="RCN_N_1"
    save_batch([raw,second],"0801")
    from landscope.db import consolidate_confirmed_properties
    with database.connect() as db:
        db.execute("""INSERT INTO property(id,sale_id,source_id,identity_status,price,area,category,share,right_type)
            SELECT 'legacy-copy',sale_id,source_id,identity_status,price,area,category,share,right_type FROM property""")
        db.execute("UPDATE observation SET property_id='legacy-copy' WHERE parcel_id=%s",(second["fields"]["dzi_id_dzialki"],))
        assert db.execute("SELECT count(*) n FROM property").fetchone()["n"]==2
        consolidate_confirmed_properties(db)
        props=db.execute("SELECT id FROM property").fetchall()
        obs=db.execute("SELECT property_id FROM observation").fetchall()
    assert len(props)==1 and {r["property_id"] for r in obs}=={props[0]["id"]}


def test_statistics_median_matches_sql(database,raw):
    save_batch([raw],"0801")
    stats=repo.statistics({"bbox":[15,52,16,53]})
    group=next(g for g in stats["groups"] if g["category"]=="unbuilt" and g["scope"]=="single")
    with database.connect() as db:
        row=db.execute("""SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY o.unit_price) AS median
            FROM observation o JOIN sale s ON s.id=o.sale_id
            WHERE o.active AND o.category='unbuilt' AND o.unit_basis IN ('parcel_price','single_parcel_land_transaction')
              AND (SELECT count(DISTINCT x.parcel_id) FROM observation x WHERE x.sale_id=o.sale_id AND x.active)=1""").fetchone()
    from decimal import Decimal
    assert group["median"]=="200.00" and Decimal(str(row["median"]))==Decimal("200")
