import json
from pathlib import Path
import pytest
from landscope.diagnostics import SOURCES,check_source

pytestmark=[pytest.mark.online,pytest.mark.contract,pytest.mark.quality]


CORE={"rcn","rcn_county","uldk","uug"}


@pytest.mark.parametrize("source",list(SOURCES))
def test_source_provides_required_data(source):
    result=check_source(source)
    folder=Path("reports/online");folder.mkdir(parents=True,exist_ok=True)
    (folder/(source+".json")).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    if source in CORE:
        assert result["status"]=="PASS",json.dumps(result,ensure_ascii=False)
    else:
        assert result["status"]=="UNAVAILABLE",json.dumps(result,ensure_ascii=False)
        assert "kontrakt" in result["reason"]
