import pytest
from landscope.card import money, area, floor_area, unit, observation_sections, parcel_sections, summary_sections, MISSING
from landscope.county import county_records
from landscope.domain import effective_unit_price

pytestmark=[pytest.mark.unit,pytest.mark.regression]

GML="""<?xml version="1.0" encoding="UTF-8"?>
<gml:FeatureCollection gml:id="o" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:rcw="https://geoportal.gov.pl/schemas/rcn/1.5">
<gml:featureMember><rcw:RCN_Transakcja gml:id="T1"><rcw:IdRCN><rcw:RCN_IdentyfikatorIIP><rcw:przestrzenNazw>TEST</rcw:przestrzenNazw>
<rcw:lokalnyId>SYNTHETIC-1</rcw:lokalnyId><rcw:wersjaId>2026-01-01T00:00:00</rcw:wersjaId></rcw:RCN_IdentyfikatorIIP></rcw:IdRCN>
<rcw:oznaczenieTransakcji>RCN_T_1</rcw:oznaczenieTransakcji><rcw:rodzajTransakcji>1</rcw:rodzajTransakcji><rcw:rodzajRynku>2</rcw:rodzajRynku>
<rcw:stronaSprzedajaca>3</rcw:stronaSprzedajaca><rcw:stronaKupujaca>4</rcw:stronaKupujaca><rcw:cenaTransakcjiBrutto>300000.00</rcw:cenaTransakcjiBrutto>
<rcw:podstawaPrawna xlink:href="D1"/><rcw:nieruchomosc xlink:href="N1"/></rcw:RCN_Transakcja></gml:featureMember>
<gml:featureMember><rcw:RCN_Dokument gml:id="D1"><rcw:oznaczenieDokumentu>AN 1/2026</rcw:oznaczenieDokumentu>
<rcw:dataSporzadzeniaDokumentu>2026-01-10</rcw:dataSporzadzeniaDokumentu><rcw:tworcaDokumentu>JAN NOTARIUSZ</rcw:tworcaDokumentu></rcw:RCN_Dokument></gml:featureMember>
<gml:featureMember><rcw:RCN_Nieruchomosc gml:id="N1"><rcw:rodzajNieruchomosci>1</rcw:rodzajNieruchomosci><rcw:rodzajPrawaDoNieruchomosci>1</rcw:rodzajPrawaDoNieruchomosci>
<rcw:udzialWPrawieDoNieruchomosci>1/1</rcw:udzialWPrawieDoNieruchomosci><rcw:polePowierzchniNieruchomosciGruntowej uom="ha">0.2000</rcw:polePowierzchniNieruchomosciGruntowej>
<rcw:cenaNieruchomosciBrutto>300000.00</rcw:cenaNieruchomosciBrutto><rcw:opis>opis testowy</rcw:opis>
<rcw:dzialka xlink:href="P1"/><rcw:dzialka xlink:href="P2"/></rcw:RCN_Nieruchomosc></gml:featureMember>
<gml:featureMember><rcw:RCN_Dzialka gml:id="P1"><rcw:idDzialki>080104_2.0002.1/1</rcw:idDzialki>
<rcw:cenaDzialkiEwidencyjnejBrutto>120000.00</rcw:cenaDzialkiEwidencyjnejBrutto><rcw:polePowierzchniEwidencyjnej uom="ha">0.1000</rcw:polePowierzchniEwidencyjnej>
<rcw:sposobUzytkowania>1</rcw:sposobUzytkowania><rcw:adresDzialki><rcw:RCN_Adres gml:id="A1"><rcw:miejscowosc>KŁODAWA</rcw:miejscowosc><rcw:ulica>TESTOWA</rcw:ulica><rcw:numerPorzadkowy>1</rcw:numerPorzadkowy></rcw:RCN_Adres></rcw:adresDzialki>
<rcw:adresDzialki><rcw:RCN_Adres gml:id="A2"><rcw:miejscowosc>KŁODAWA</rcw:miejscowosc><rcw:ulica>TESTOWA</rcw:ulica><rcw:numerPorzadkowy>1A</rcw:numerPorzadkowy></rcw:RCN_Adres></rcw:adresDzialki>
</rcw:RCN_Dzialka></gml:featureMember>
<gml:featureMember><rcw:RCN_Dzialka gml:id="P2"><rcw:idDzialki>080104_2.0002.1/2</rcw:idDzialki>
<rcw:polePowierzchniEwidencyjnej uom="m2">1000</rcw:polePowierzchniEwidencyjnej><rcw:sposobUzytkowania>1</rcw:sposobUzytkowania></rcw:RCN_Dzialka></gml:featureMember>
</gml:FeatureCollection>""".encode("utf-8")


@pytest.fixture
def records():
    rows,_=county_records(GML,"2026-02-01")
    from landscope.sources import normalize_rcn
    return {r["fields"]["dzi_id_dzialki"]:normalize_rcn(r["fields"],r["feature_id"],r["geometry"]) for r in rows}


def test_formats():
    assert money("335000") == "335 000,00 zł"
    assert area("1903.0000") == "19,03 ara" and area("50") == "0,50 ara"
    assert area("100") == "1 ar" and area("200") == "2 ary" and area("500") == "5 arów"
    assert floor_area("50") == "50 m²"
    assert unit("215.4493") == "21 544,93 zł/ar"


def test_parcel_price_field_and_details(records):
    first=records["080104_2.0002.1/1"]
    # Regression: schema 1.5 calls it cenaDzialkiEwidencyjnejBrutto; the old name silently dropped all 1550 parcel prices.
    assert first["price"]=="120000.00"
    assert first["address"]=="KŁODAWA TESTOWA 1; KŁODAWA TESTOWA 1A"
    tx=first["details"]["transaction"]
    assert tx["seller_type"]=="osobaFizyczna" and tx["buyer_type"]=="osobaPrawna" and tx["document"]=="AN 1/2026"
    assert "JAN NOTARIUSZ" not in str(first)
    assert first["details"]["property"]["description"]=="opis testowy"


def test_package_never_allocated(records):
    first,second=records["080104_2.0002.1/1"],records["080104_2.0002.1/2"]
    assert effective_unit_price(first)==(120,"parcel_price")
    value,basis=effective_unit_price(second)
    # No own price: whole-act price over all parcel areas, labelled as a package and kept out of medians.
    assert basis=="package_land_transaction" and value==300000/2000


def test_card_rows_unique_and_complete(records):
    first=records["080104_2.0002.1/1"]
    sections=observation_sections("sale.0",first,{"sale_date":"2026-01-10","price":"300000.00"},"RCN")
    rows={r["key"]:r for s in sections for r in s["rows"]}
    assert len(rows)==sum(len(s["rows"]) for s in sections)
    assert rows["sale.0.transaction.price"]["value"]=="300 000,00 zł"
    assert rows["sale.0.parcel.price"]["value"]=="120 000,00 zł"
    assert rows["sale.0.parcel.unit_price"]["value"]=="12 000,00 zł/ar" and rows["sale.0.parcel.unit_price"]["status"]=="inferred"
    assert rows["sale.0.related.0"]["link"]=="080104_2.0002.1/2"
    assert rows["sale.0.transaction.vat"]["value"]==MISSING and rows["sale.0.transaction.vat"]["status"]=="unavailable"
    parcel=parcel_sections({"id":"080104_2.0002.1/1","number":"1/1"},first,[],None,None,None)
    keys=[r["key"] for s in parcel for r in s["rows"]]
    prow={r["key"]:r for s in parcel for r in s["rows"]}
    assert len(keys)==len(set(keys)) and "context.current_plan" in keys
    assert prow["parcel.owner"]["value"]=="Osoba prawna"


def test_summary_price_date_and_owners(records):
    first=records["080104_2.0002.1/1"]
    observations=[{"sale_id":"s1","sale_date":"2026-01-10","price":"300000.00","payload":first}]
    rows={r["key"]:r for s in summary_sections(observations,[], "0002") for r in s["rows"]}
    assert rows["summary.last_price"]["sub"]=="2026-01-10"
    assert rows["summary.unit_price"]["value"]=="12 000,00 zł/ar"
    assert rows["owners.0"]["value"]=="Osoba fizyczna → Osoba prawna"
