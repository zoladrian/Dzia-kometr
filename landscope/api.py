from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db, repository as repo
from .domain import ContractError, parcel_id
from .sources import lookup_parcel, Unavailable
from .diagnostics import SOURCES

log = logging.getLogger(__name__)


def bbox_value(value):
    try:
        values = [float(n) for n in value.split(",")]
        if len(values)!=4 or not (-180<=values[0]<values[2]<=180 and -90<=values[1]<values[3]<=90):
            raise ValueError()
        return values
    except (ValueError,TypeError):
        raise HTTPException(422,"bbox musi mieć postać zachód,południe,wschód,północ")


class Filter(BaseModel):
    bbox: str
    limit: int = Field(default=50,ge=1,le=200)
    offset: int = Field(default=0,ge=0)
    sort: Literal["date","price","area"] = "date"
    order: Literal["asc","desc"] = "desc"
    zoom: int = Field(default=12,ge=0,le=22)
    date_from: date | None = None
    date_to: date | None = None
    price_min: Decimal | None = Field(default=None,ge=0)
    price_max: Decimal | None = Field(default=None,ge=0)
    area_min: Decimal | None = Field(default=None,ge=0)
    area_max: Decimal | None = Field(default=None,ge=0)
    category: Literal["unbuilt","built","unknown"] | None = None
    place: str | None = Field(default=None,max_length=200)
    land_use: str | None = Field(default=None,max_length=200)
    county: str | None = Field(default=None,pattern=r"^\d{4}$")
    counties: str | None = Field(default=None,pattern=r"^(\d{4})(,\d{4})*$")
    polygon: str | None = Field(default=None,max_length=20000)
    unit_min: Decimal | None = Field(default=None,ge=0)
    unit_max: Decimal | None = Field(default=None,ge=0)
    categories: str | None = Field(default=None,pattern=r"^(unbuilt|built|unknown)(,(unbuilt|built|unknown))*$")

    def filters(self):
        result = self.model_dump(exclude_none=True,exclude={"limit","offset","sort","order","zoom"})
        result["bbox"] = bbox_value(self.bbox)
        if self.categories:
            result["categories"] = self.categories.split(",")
        if self.counties:
            result["counties"] = self.counties.split(",")
        for low,high in (("date_from","date_to"),("price_min","price_max"),("area_min","area_max"),("unit_min","unit_max")):
            if result.get(low) is not None and result.get(high) is not None and result[low]>result[high]:
                raise HTTPException(422,f"{low} musi być <= {high}")
        if self.polygon:
            from .geometry import validate_geojson
            try:
                parsed = json.loads(self.polygon)
            except json.JSONDecodeError as exc:
                raise HTTPException(422,"Nieprawidłowy wielokąt") from exc
            if not isinstance(parsed,dict) or parsed.get("type") not in {"Polygon","MultiPolygon"}:
                raise HTTPException(422,"Nieprawidłowy wielokąt")
            try:
                result["polygon"] = validate_geojson(parsed,polygon_only=True)
            except (ValueError,KeyError,TypeError,ContractError) as exc:
                raise HTTPException(422,"Nieprawidłowy wielokąt") from exc
        return result


class FavoriteInput(BaseModel):
    label: str = Field(default="",max_length=120)


class CountySelection(BaseModel):
    selected: list[str] = Field(min_length=1,max_length=40)


class CountyImport(BaseModel):
    codes: list[str] = Field(min_length=1,max_length=8)
    force: bool = False


def exact(value):
    return JSONResponse(content=jsonable_encoder(value,custom_encoder={Decimal:str}))


def create_app(initialize=True):
    @asynccontextmanager
    async def lifespan(app):
        if initialize:
            import time
            last = None
            for attempt in range(12):
                try:
                    db.initialize()
                    last = None
                    break
                except Exception as exc:
                    last = exc
                    log.warning("Baza jeszcze niegotowa (%s/12): %s", attempt + 1, exc)
                    time.sleep(2)
            if last is not None:
                log.error("Baza nie jest gotowa; /api/health zwróci 503: %s", last)
        yield

    app = FastAPI(title="LandScope",version="0.1.0",lifespan=lifespan)
    static = Path(__file__).parent/"static"
    static.mkdir(exist_ok=True)
    app.mount("/static",StaticFiles(directory=static),name="static")

    @app.exception_handler(ContractError)
    async def contract_error(request,exc):
        return JSONResponse(status_code=422,content={"detail":str(exc)})

    @app.exception_handler(Unavailable)
    async def unavailable(request,exc):
        return JSONResponse(status_code=503,content={"detail":str(exc),"status":"UNAVAILABLE"})

    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        log.exception("Błąd obsługi żądania",exc_info=exc)
        return JSONResponse(status_code=503,content={"detail":"Usługa lub baza jest niedostępna. Sprawdź /api/health i logi.","status":"UNAVAILABLE"})

    @app.get("/")
    def index():
        return FileResponse(static/"index.html")

    @app.get("/api/health")
    def health():
        try:
            with db.connect() as conn:
                version = conn.execute("SELECT postgis_version() AS version").fetchone()["version"]
            return {"status":"PASS","database":"PostgreSQL/PostGIS","postgis":version}
        except Exception as exc:
            return JSONResponse(status_code=503,content={"status":"UNAVAILABLE","database":"unavailable","reason":type(exc).__name__})

    @app.get("/api/counts")
    def counts():
        return db.counts()

    @app.get("/api/sources")
    def sources():
        report = Path("reports/sources.json")
        checked = {r["source"]:r for r in json.loads(report.read_text(encoding="utf-8"))} if report.exists() else {}
        return [checked.get(name,{"source":name,**entry,"status":"UNAVAILABLE","checked_at":None,"reason":"Nie uruchomiono diagnostyki CLI"}) for name,entry in SOURCES.items()]

    @app.get("/api/quality")
    def quality():
        return exact(repo.quality_report())

    @app.get("/api/transactions")
    def transactions(filters: Filter = Query()):
        return exact(repo.transactions(filters.filters(),filters.limit,filters.offset,filters.sort,filters.order))

    @app.get("/api/transactions/{identifier}")
    def transaction(identifier:str):
        result = repo.transaction_detail(identifier)
        if result is None:
            raise HTTPException(404,"Nie znaleziono transakcji")
        return exact(result)

    @app.get("/api/map")
    def map_data(filters:Filter=Query()):
        return exact(repo.map_features(filters.filters(),filters.zoom))

    @app.get("/api/statistics")
    def statistics(filters:Filter=Query()):
        return exact(repo.statistics(filters.filters()))

    @app.get("/api/parcels/search")
    def search(q:str=Query(min_length=1,max_length=150),commune:str|None=None,online:bool=True):
        local = repo.search_local(q,commune)
        if local and (not online or all(r["geometry"] for r in local)):
            return {"items":local,"source":"local"}
        if not online:
            return {"items":local,"source":"local"}
        try:
            found = lookup_parcel(q)
            if commune:
                found = [r for r in found if commune.casefold() in r["commune"].casefold()]
            for item in found:
                repo.save_parcel(item)
            return {"items":found,"source":"uldk"}
        except Unavailable:
            if local:
                return {"items":local,"source":"local","warning":"ULDK niedostępny; zapisane dane mogą być nieaktualne"}
            raise

    @app.get("/api/parcels/at-point")
    def at_point(lon:float=Query(ge=14,le=25),lat:float=Query(ge=49,le=55)):
        found = lookup_parcel(xy=(lon,lat))
        for item in found:
            repo.save_parcel(item)
        return {"items":found}

    @app.get("/api/bounds")
    def bounds(place:str=Query(min_length=2,max_length=200)):
        result = repo.bounds({"place":place})
        if result is None:
            raise HTTPException(404,"Brak transakcji dla tej nazwy")
        return exact(result)

    @app.get("/api/address")
    def address(q:str=Query(min_length=3,max_length=200)):
        return {"items":repo.parcels_for_address(q)}

    @app.get("/api/parcel/card")
    def parcel_card(id:str):
        result = repo.parcel_card(parcel_id(id))
        if result is None:
            raise HTTPException(404,"Nie znaleziono działki")
        return exact(result)

    @app.get("/api/transactions/{identifier}/card")
    def transaction_card(identifier:str):
        result = repo.transaction_card(identifier)
        if result is None:
            raise HTTPException(404,"Nie znaleziono transakcji")
        return exact(result)

    # Query parameter instead of a path: parcel identifiers contain '/'.
    @app.get("/api/parcel")
    def parcel(id:str):
        result = repo.parcel_detail(parcel_id(id))
        if result is None:
            raise HTTPException(404,"Nie znaleziono działki")
        return exact(result)

    @app.get("/api/counties")
    def counties():
        from . import powiaty
        return exact(powiaty.overview())

    @app.put("/api/counties")
    def set_counties(body: CountySelection):
        from . import powiaty
        selected = powiaty.save_selected(body.selected)
        return exact(powiaty.overview() | {"selected": selected})

    @app.post("/api/counties/import")
    def import_counties(body: CountyImport):
        from . import powiaty
        return exact(powiaty.start_import(body.codes, force=body.force))

    @app.get("/api/favorites")
    def favorites():
        return repo.favorites()

    @app.put("/api/favorite")
    def favorite(id:str,body:FavoriteInput):
        if repo.parcel_detail(parcel_id(id)) is None:
            raise HTTPException(404,"Najpierw wyszukaj działkę")
        repo.set_favorite(id,body.label)
        return {"saved":True}

    @app.delete("/api/favorite")
    def remove_favorite(id:str):
        repo.set_favorite(parcel_id(id))
        return {"deleted":True}

    return app


app = create_app()
