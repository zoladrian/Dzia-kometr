from landscope.powiaty import catalog, parse_codes, PINNED
from landscope.domain import ContractError
import pytest


def test_catalog_pins_gorzowski_and_minski_first():
    items = catalog()
    assert len(items) == 380
    assert [i["code"] for i in items[:2]] == list(PINNED) == ["0801", "1412"]
    assert items[0]["label"] == "powiat gorzowski"
    assert items[1]["label"] == "powiat miński"
    assert "Arynów" in items[1]["hint"]
    assert items[0]["pinned"] and items[1]["pinned"]
    assert not items[2]["pinned"]
    by_code = {item["code"]: item for item in items}
    assert by_code["0201"]["label"] == "powiat bolesławiecki"
    assert by_code["0264"]["label"] == "Wrocław"
    assert by_code["0264"]["hint"] == "miasto na prawach powiatu"


def test_parse_codes_rejects_unknown():
    assert parse_codes(["0801", "1412", "0801"]) == ["0801", "1412"]
    with pytest.raises(ContractError):
        parse_codes(["9999"])
    with pytest.raises(ContractError):
        parse_codes(["801"])
