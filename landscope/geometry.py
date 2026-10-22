"""GML authority axis order is different from GeoJSON's longitude, latitude."""
import re
from functools import lru_cache
from .domain import ContractError


def local(tag):
    return tag.rsplit("}", 1)[-1]


@lru_cache(maxsize=32)
def transformer(srs):
    from pyproj import CRS, Transformer
    return Transformer.from_crs(CRS.from_user_input(srs), "EPSG:4326", always_xy=False)


def validate_geojson(value, polygon_only=False):
    from shapely.geometry import shape, mapping
    geometry = shape(value)
    if geometry.is_empty or not geometry.is_valid:
        raise ContractError("Pusta lub nieprawidłowa geometria")
    if polygon_only and geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ContractError("Wymagana granica działki (Polygon/MultiPolygon)")
    if geometry.geom_type not in {"Point", "Polygon", "MultiPolygon", "MultiPoint"}:
        raise ContractError("Nieobsługiwany typ geometrii")
    x1,y1,x2,y2 = geometry.bounds
    if not (13 <= x1 <= x2 <= 25 and 48 <= y1 <= y2 <= 56):
        raise ContractError("Geometria poza Polską lub błędna kolejność osi/CRS")
    return mapping(geometry)


def gml_geometry(element):
    nodes = [e for e in element.iter() if local(e.tag) in {"Point", "Polygon", "MultiSurface", "MultiPolygon", "MultiPoint"}]
    if not nodes:
        return None
    from pyproj import CRS, Transformer
    root = nodes[0]
    srs = next((e.get("srsName") for e in [root, *element.iter()] if e.get("srsName")), None)
    if not srs:
        raise ContractError("Geometria bez srsName")
    transform = transformer(srs)
    def coordinates(node):
        positions = [n for n in node.iter() if local(n.tag) in {"pos", "posList", "coordinates"}]
        pos = positions[0] if positions else None
        if pos is None or not pos.text:
            raise ContractError("Geometria bez współrzędnych")
        dim = int(pos.get("srsDimension", root.get("srsDimension", "2")))
        if dim != 2:
            raise ContractError("Obsługiwane są wyłącznie współrzędne 2D")
        data = [float(n) for p in positions for n in re.split(r"[\s,]+", (p.text or "").strip())]
        if len(data) % 2:
            raise ContractError("Nieparzysta liczba współrzędnych")
        result = []
        for a,b in zip(data[::2], data[1::2]):
            lat,lon = transform.transform(a,b)
            result.append([lon,lat])
        return result
    def polygon(node):
        rings = [n for n in node.iter() if local(n.tag) == "LinearRing"]
        if not rings:
            raise ContractError("Wielokąt bez pierścienia")
        result = [coordinates(r) for r in rings]
        if any(len(r) < 4 or r[0] != r[-1] for r in result):
            raise ContractError("Niezamknięty pierścień")
        return result
    kind = local(root.tag)
    if kind == "Point":
        result = {"type":"Point","coordinates":coordinates(root)[0]}
    elif kind == "MultiPoint":
        result = {"type":"MultiPoint","coordinates":[coordinates(n)[0] for n in root.iter() if local(n.tag) == "Point"]}
    elif kind == "Polygon":
        result = {"type":"Polygon","coordinates":polygon(root)}
    else:
        result = {"type":"MultiPolygon","coordinates":[polygon(n) for n in root.iter() if local(n.tag) == "Polygon"]}
    return validate_geojson(result)


def uldk_wkt(text):
    from shapely import wkt
    from shapely.geometry import mapping
    # ULDK requested explicitly in EPSG:4326; WKT uses X,Y.
    if text.startswith("SRID="):
        srid,text = text.split(";",1)
        if srid != "SRID=4326":
            raise ContractError("Nieoczekiwany SRID ULDK")
    try:
        return validate_geojson(mapping(wkt.loads(text)), polygon_only=True)
    except Exception as exc:
        if isinstance(exc, ImportError):
            raise
        raise ContractError("Nieprawidłowa geometria ULDK") from exc
