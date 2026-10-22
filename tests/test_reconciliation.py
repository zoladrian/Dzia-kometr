import pytest
from pathlib import Path
from landscope.db import connect
from landscope.domain import FOLD_FROM, FOLD_TO
from landscope.sources import normalize_rcn
from landscope.county import county_records

pytestmark=[pytest.mark.online,pytest.mark.real_data,pytest.mark.quality,pytest.mark.regression]


def test_saved_klodawa_records_match_county_gml():
    with connect() as db:
        run=db.execute("""SELECT report FROM import_run WHERE status='complete' AND report ? 'archive'
          ORDER BY finished_at DESC LIMIT 1""").fetchone()
        records=db.execute("""SELECT feature_id,payload FROM observation WHERE active
          AND lower(translate(address,%s,%s)) LIKE %s
          ORDER BY md5(feature_id || '8012026') LIMIT 5""",(FOLD_FROM,FOLD_TO,"%klodawa%")).fetchall()
    assert run,"UNAVAILABLE: brak zakończonego importu GML powiatu"
    assert len(records)==5,"UNAVAILABLE: brak zapisanych rzeczywistych rekordów Kłodawy"
    rows,_=county_records(Path(run["report"]["archive"]).read_bytes(),run["report"].get("snapshot"))
    by_id={row["feature_id"]:row for row in rows}
    for record in records:
        source=by_id[record["feature_id"]]
        fresh=normalize_rcn(source["fields"],source["feature_id"],source["geometry"])
        for key in ("transaction_source_id","namespace","parcel_id","date","price","transaction_price","property_price","area","share","source_version"):
            assert fresh[key]==record["payload"][key],f"Rozbieżność GML / baza: {key}"
