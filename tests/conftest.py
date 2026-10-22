import os
import re
import uuid
import pytest


def pytest_addoption(parser):
    for name in ("online","integration","e2e","real-data"):
        parser.addoption("--"+name,action="store_true",default=False)


def pytest_collection_modifyitems(config,items):
    for item in items:
        for mark,flag in (("online","online"),("integration","integration"),("e2e","e2e"),("real_data","real-data")):
            if mark in item.keywords and not config.getoption("--"+flag):
                item.add_marker(pytest.mark.skip(reason="Wymaga jawnego --"+flag+"; NIE URUCHOMIONO"))


@pytest.fixture
def fields():
    # Explicitly synthetic contract fixture; never imported into production.
    return {"tran_lokalny_id_iip":"TEST-T1","tran_przestrzen_nazw":"TEST-RCN",
            "tran_wersja_id":"2025-01-01T00:00:00","dok_data":"2024-06-12",
            "dzi_id_dzialki":"080104_2.0001.123/4","dzi_pow_ewid":"1000.00",
            "dzi_cena_brutto":"200000.00","tran_cena_brutto":"500000.00",
            "nier_cena_brutto":"500000.00","nier_pow_gruntu":"2500.00",
            "nier_udzial":"1/1","nier_prawo":"własność","nier_rodzaj":"grunt niezabudowany",
            "dzi_adres":"Kłodawa","dzi_sposob_uzyt":"rolny","tran_rodzaj_rynku":"wolny"}


@pytest.fixture
def raw(fields):
    return {"fields":fields,"feature_id":"dzialki.TEST-1",
            "geometry":{"type":"Point","coordinates":[15.214,52.786]},
            "geometry_error":None,"raw_xml":"<SYNTHETIC/>"}


@pytest.fixture
def database(monkeypatch):
    try:
        import psycopg
        from psycopg.conninfo import make_conninfo
        from landscope import db
        original=db.database_url()
        schema="landscope_test_"+uuid.uuid4().hex
        with db.connect(original) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            conn.execute('CREATE SCHEMA "'+schema+'"')
    except Exception as exc:
        pytest.fail("UNAVAILABLE: rzeczywisty PostgreSQL/PostGIS: "+str(exc),pytrace=False)
    monkeypatch.setenv("DATABASE_URL",make_conninfo(original,options="-c search_path="+schema+",public"))
    db.initialize()
    try:
        yield db
    finally:
        assert re.fullmatch(r"landscope_test_[a-f0-9]{32}",schema)
        with db.connect(original) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')
