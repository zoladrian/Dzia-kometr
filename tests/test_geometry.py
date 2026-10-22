import pytest
from landscope.sources import xml, parse_uldk
from landscope.geometry import gml_geometry,validate_geojson
from landscope.domain import ContractError

pytestmark=[pytest.mark.contract,pytest.mark.quality]


def test_gml_authority_axis_order():
    root=xml(b'<Point xmlns="http://www.opengis.net/gml/3.2" srsName="urn:ogc:def:crs:EPSG::4326"><pos>52.786 15.214</pos></Point>')
    assert tuple(gml_geometry(root)["coordinates"])==(15.214,52.786)


def test_gml_missing_crs_and_wrong_axes():
    with pytest.raises(ContractError): gml_geometry(xml(b'<Point><pos>15 52</pos></Point>'))
    with pytest.raises(ContractError): gml_geometry(xml(b'<Point srsName="EPSG:4326"><pos>15 52</pos></Point>'))


def test_uldk_wkt_polygon_and_id():
    text="0\n080104_2.0001.123/4|Kłodawa|Kłodawa|123/4|POLYGON ((15.21 52.78,15.22 52.78,15.22 52.79,15.21 52.78))|powiat"
    assert parse_uldk(text,query="080104_2.0001.123/4")[0]["geometry_kind"]=="parcel_boundary"
    with pytest.raises(ContractError): parse_uldk(text,query="080104_2.0001.123/5")


@pytest.mark.parametrize("value",[
 {"type":"Point","coordinates":[52,15]},
 {"type":"Polygon","coordinates":[[[15,52],[16,53],[16,52],[15,53],[15,52]]]},
 {"type":"Polygon","coordinates":[]},
])
def test_invalid_geometries(value):
    with pytest.raises(ContractError): validate_geojson(value)
