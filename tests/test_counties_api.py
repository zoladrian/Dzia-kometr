from fastapi.testclient import TestClient
from landscope.api import create_app


def test_counties_unknown_rejected_without_db():
    client=TestClient(create_app(initialize=False),raise_server_exceptions=False)
    assert client.put("/api/counties",json={"selected":[]}).status_code==422
    assert client.post("/api/counties/import",json={"codes":["xxxx"]}).status_code==422
