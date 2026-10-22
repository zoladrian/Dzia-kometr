import pytest
from fastapi.testclient import TestClient
from landscope.sources import xml, rcn_schema, rcn_page, normalize_rcn, rcn_params, parse_uldk, Unavailable
from landscope.domain import ContractError,unit_price
from landscope.api import create_app,Filter

pytestmark=[pytest.mark.contract,pytest.mark.regression]


def test_reject_html_xml_exception_and_entities():
    for content in (b"<html>error</html>",b'<ExceptionReport>failure</ExceptionReport>',b'<!DOCTYPE x [<!ENTITY e "bad">]><x/>'):
        with pytest.raises(ContractError): rcn_page(content)


def test_schema_drift():
    with pytest.raises(ContractError):
        rcn_schema(b'<schema xmlns="http://www.w3.org/2001/XMLSchema"><element name="unknown"/></schema>')


def test_required_identity(fields):
    fields.pop("tran_lokalny_id_iip")
    with pytest.raises(ContractError): normalize_rcn(fields,"fid")


def test_scope_separation(fields):
    item=normalize_rcn(fields,"fid")
    assert item["transaction_price"]=="500000.00"
    assert item["price"]=="200000.00"
    assert item["property_identity"]=="unavailable"
    fields["dzi_cena_brutto"]=None
    item=normalize_rcn(fields,"fid")
    assert item["price"] is None
    assert unit_price(item["price"],item["area"],scope="parcel",share=item["share"],category=item["category"]) is None


@pytest.mark.quality
def test_missing_nonpositive_fields(fields):
    fields["dzi_pow_ewid"]="-12";fields["dok_data"]=None;fields["dzi_cena_brutto"]="0"
    item=normalize_rcn(fields,"fid")
    assert {"area_nonpositive","date_missing","price_nonpositive","geometry_missing"}<=set(item["issues"])


def test_uldk_rejects_error_and_html():
    with pytest.raises(Unavailable): parse_uldk("-1\nBrak działki")
    with pytest.raises(ContractError): parse_uldk("<html>error</html>")
    with pytest.raises(ContractError): parse_uldk("0\nshort|answer")


def test_county_filter_and_paging():
    a=rcn_params("0801",500,100)
    assert "0801*" in a["filter"] and a["startIndex"]==500 and a["count"]==100
    with pytest.raises(ContractError): rcn_params("0801<evil>")


def test_api_contract_validation():
    # Contract-only client. No claim that a mocked database is integration coverage.
    client=TestClient(create_app(initialize=False),raise_server_exceptions=False)
    for query in ("","?bbox=bad","?bbox=16,53,15,52","?bbox=14,52,16,53&limit=201",
                  "?bbox=14,52,16,53&price_min=-1","?bbox=14,52,16,53&sort=sql",
                  "?bbox=14,52,16,53&date_from=2025-01-01&date_to=2024-01-01",
                  "?bbox=14,52,16,53&counties=bad"):
        assert client.get("/api/transactions"+query).status_code==422
    assert client.get("/api/map?bbox=14,52,16,53&zoom=99").status_code==422
    assert client.get("/api/parcel?id=garbage").status_code==422
    for poly in ("{}","null","[]","1","{\"type\":\"Point\",\"coordinates\":[15,52]}"):
        assert client.get("/api/transactions?bbox=14,52,16,53&polygon="+poly).status_code==422,poly
        assert client.get("/api/map?bbox=14,52,16,53&polygon="+poly).status_code==422,poly
        assert client.get("/api/statistics?bbox=14,52,16,53&polygon="+poly).status_code==422,poly


def test_api_response_contract_and_pagination(monkeypatch):
    from landscope import repository
    calls=[]
    def fake(filters,limit,offset,sort,order):
        calls.append((filters,limit,offset,sort,order))
        return {"items":[],"total":0,"limit":limit,"offset":offset}
    monkeypatch.setattr(repository,"transactions",fake)
    client=TestClient(create_app(initialize=False))
    result=client.get("/api/transactions?bbox=14,52,16,53&limit=10&offset=20&category=unbuilt&place=K%C5%82odawa")
    assert result.status_code==200 and result.json()=={"items":[],"total":0,"limit":10,"offset":20}
    assert calls[0][0]["bbox"]==[14,52,16,53]
    assert calls[0][0]["place"]=="Kłodawa"


def test_raw_personal_fields_not_public(fields):
    fields["tran_kupujacy"]="PRIVATE PERSON"
    fields["dok_tworca"]="PRIVATE NOTARY"
    item=normalize_rcn(fields,"fid")
    assert "PRIVATE" not in str(item)


def test_api_money_keeps_decimal_precision(monkeypatch):
    from decimal import Decimal
    from landscope import repository
    monkeypatch.setattr(repository,"transaction_detail",lambda _:{"price":Decimal("123456789012345.67")})
    client=TestClient(create_app(initialize=False))
    assert client.get("/api/transactions/test").json()["price"]=="123456789012345.67"
