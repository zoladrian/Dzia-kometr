import os
from pathlib import Path


def database_url():
    # Bind is IPv4-only (compose 127.0.0.1:15432). `localhost` can resolve to ::1 on Windows and hang.
    url = os.getenv("DATABASE_URL", "postgresql://landscope:landscope_local@127.0.0.1:15432/landscope")
    return url.replace("@localhost:", "@127.0.0.1:").replace("@localhost/", "@127.0.0.1/")


def data_dir():
    path = Path(os.getenv("LANDSCOPE_DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


RCN_URL = "https://mapy.geoportal.gov.pl/wss/service/rcn"
ULDK_URL = "https://uldk.gugik.gov.pl/"
COUNTY = os.getenv("LANDSCOPE_COUNTY", "0801")
