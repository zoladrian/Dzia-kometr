from decimal import Decimal
import pytest
from landscope.domain import number, money, full_share, unit_price, distribution, parcel_id, sale_date, ContractError, land_category

pytestmark=[pytest.mark.unit,pytest.mark.regression]


@pytest.mark.parametrize("price,area,result",[("100","3","33.33"),("0.01","2","0.01"),("200000","1000","200.00")])
def test_exact_calculation(price,area,result):
    assert money(unit_price(price,area,scope="parcel",share="1/1",category="unbuilt"))==result


@pytest.mark.parametrize("scope,share,category,price,area",[
 ("transaction","1","unbuilt","100","1"),("parcel",None,"unbuilt","100","1"),
 ("parcel","1/2","unbuilt","100","1"),("parcel","1","unknown","100","1"),
 ("parcel","1","unbuilt","-1","1"),("parcel","1","unbuilt","100","0"),
 ("parcel","1","unbuilt",None,"100"),("parcel","1","unbuilt","100",None)])
def test_no_unjustified_unit_price(scope,share,category,price,area):
    assert unit_price(price,area,scope=scope,share=share,category=category) is None


@pytest.mark.parametrize("value",["NaN","Infinity","-Infinity","abc"])
def test_invalid_numbers(value):
    with pytest.raises(ContractError): number(value)


def test_decimal_input_and_rounding():
    assert number("1 234,56")==Decimal("1234.56")
    assert money(Decimal("2.345"))=="2.35"


def test_full_share():
    assert full_share("3/3")
    assert not full_share("1/0")
    assert not full_share("")
    assert not full_share("2")


def test_distribution_regression():
    result=distribution(["10","10","20","60"])
    assert result["median"]=="15.00"
    assert result["min"]=="10.00" and result["max"]=="60.00"
    assert sum(b["count"] for b in result["histogram"])==4
    assert distribution([])["median"] is None
    assert sum(b["count"] for b in distribution(["7","7"])["histogram"])==2


def test_identifier_and_unknown_dictionary():
    assert parcel_id("080104_2.0001.123/4")
    assert parcel_id("080104_2.0001.AR_1.123/4")
    with pytest.raises(ContractError): parcel_id("123/4")
    assert land_category("1")=="unknown"
    assert land_category("grunt niezabudowany")=="unbuilt"
    assert land_category("grunt zabudowany")=="built"


def test_future_and_missing_date():
    assert sale_date(None) is None
    with pytest.raises(ContractError): sale_date("2999-01-01")
