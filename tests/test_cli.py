import sys
import pytest

pytestmark=[pytest.mark.unit,pytest.mark.regression]


def test_cli_test_forwards_pytest_args(monkeypatch):
    from landscope import cli
    called=[]
    monkeypatch.setattr(sys,"argv",["landscope","test","-m","unit"])
    monkeypatch.setattr("pytest.main",lambda args: called.append(list(args)) or 0)
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code==0
    assert called==[["-m","unit"]]
