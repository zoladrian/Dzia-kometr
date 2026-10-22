"""Offline orchestration regressions; HTTP and DB are replaced only in this file."""
import xml.etree.ElementTree as ET
import httpx
import pytest
from landscope import importer
from landscope.sources import rcn_page,normalize_rcn,Unavailable
from landscope.domain import ContractError

pytestmark=[pytest.mark.regression,pytest.mark.contract]


def page(fields,fid,total=1):
    root=ET.Element("{http://www.opengis.net/wfs/2.0}FeatureCollection",numberMatched=str(total),numberReturned="1")
    member=ET.SubElement(root,"{http://www.opengis.net/wfs/2.0}member")
    feature=ET.SubElement(member,"{http://mapserver.gis.umn.edu/mapserver}dzialki",{"{http://www.opengis.net/gml/3.2}id":fid})
    for k,v in fields.items():
        child=ET.SubElement(feature,"{http://mapserver.gis.umn.edu/mapserver}"+k)
        child.text=v
    return ET.tostring(root)


def schema():
    names=["tran_lokalny_id_iip","tran_przestrzen_nazw","dok_data","dzi_id_dzialki","dzi_pow_ewid","dzi_cena_brutto"]
    return ('<schema xmlns="http://www.w3.org/2001/XMLSchema">'+''.join('<element name="'+n+'"/>' for n in names)+'</schema>').encode()


def test_real_parser_synthetic_contract(fields):
    rows,total=rcn_page(page(fields,"F1"))
    assert total==1 and len(rows)==1
    normalized=normalize_rcn(rows[0]["fields"],rows[0]["feature_id"],rows[0]["geometry"])
    assert normalized["price"]=="200000.00"
    assert normalized["transaction_price"]=="500000.00"
    assert "geometry_missing" in normalized["issues"]


def test_declared_row_count_must_match(fields):
    content=page(fields,"F1").replace(b'numberReturned="1"',b'numberReturned="2"')
    with pytest.raises(ContractError): rcn_page(content)


def test_resume_after_interruption_and_no_early_promotion(tmp_path,monkeypatch,fields):
    monkeypatch.setattr(importer,"data_dir",lambda:tmp_path)
    monkeypatch.setattr(importer,"initialize",lambda:None)
    calls=[];promotions=[];fail=[True]
    def fetch(url,params):
        calls.append(params.copy())
        if params["request"]=="DescribeFeatureType":
            content=schema()
        elif params["startIndex"]==0:
            content=page(fields,"F1",2)
        elif fail[0]:
            raise Unavailable("TEST interrupted connection")
        else:
            second=fields.copy();second["dzi_id_dzialki"]="080104_2.0001.124"
            content=page(second,"F2",2)
        return httpx.Response(200,content=content,request=httpx.Request("GET",url))
    def archive(response,source):
        name=tmp_path/("archive-"+str(len(calls))+".xml");name.write_bytes(response.content);return str(name)
    def save(records,county):
        promotions.append(records)
        return {"complete":True}
    monkeypatch.setattr(importer,"fetch",fetch);monkeypatch.setattr(importer,"archive",archive);monkeypatch.setattr(importer,"save_batch",save)
    with pytest.raises(Unavailable): importer.import_rcn("0801",page_size=1)
    assert not promotions
    download_id=next((tmp_path/"imports").iterdir()).name
    fail[0]=False
    result=importer.import_rcn("0801",resume=download_id,page_size=1)
    assert result["complete"] and len(promotions[0])==2
    assert sum(p.get("startIndex")==0 for p in calls)==1


def test_repeated_wfs_page_is_not_success(tmp_path,monkeypatch,fields):
    monkeypatch.setattr(importer,"data_dir",lambda:tmp_path)
    monkeypatch.setattr(importer,"initialize",lambda:None)
    def fetch(url,params):
        return httpx.Response(200,content=schema() if params["request"]=="DescribeFeatureType" else page(fields,"SAME",2),
                              request=httpx.Request("GET",url))
    count=[0]
    def archive(response,source):
        count[0]+=1;name=tmp_path/str(count[0]);name.write_bytes(response.content);return str(name)
    monkeypatch.setattr(importer,"fetch",fetch);monkeypatch.setattr(importer,"archive",archive)
    with pytest.raises(ContractError,match="WFS"):
        importer.import_rcn("0801",page_size=1)
