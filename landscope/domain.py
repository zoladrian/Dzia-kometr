"""Exact arithmetic and conservative scope rules. Never allocate transaction prices."""
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
from statistics import median


class ContractError(ValueError):
    pass


def number(value):
    if value is None or str(value).strip() in ("", "null", "None"):
        return None
    try:
        result = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ContractError("Nieprawidłowa liczba") from exc
    if not result.is_finite():
        raise ContractError("Liczba NaN/Infinity")
    return result


def money(value):
    return None if value is None else str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def full_share(value):
    if value is None or str(value).strip() == "":
        return False
    try:
        parts = str(value).split("/")
        return (number(parts[0]) / number(parts[1]) if len(parts) == 2 else number(value)) == 1
    except (ArithmeticError, ContractError, TypeError):
        return False


def unit_price(price, area, *, scope, share, category):
    price, area = number(price), number(area)
    if scope not in {"parcel", "property", "transaction_complete_land"}:
        return None
    if category not in {"unbuilt", "built"} or not full_share(share):
        return None
    if price is None or area is None or price <= 0 or area <= 0:
        return None
    return price / area


UNIT_BASIS = {
    "parcel_price": "Cena tej działki z RCN / jej powierzchnia ewidencyjna",
    "single_parcel_land_transaction": "Cena całego aktu / powierzchnia jedynej działki; akt obejmuje wyłącznie ten grunt w całości",
    "package_land_transaction": "Cena całego aktu / suma powierzchni wszystkich działek aktu (pakiet; poza medianą)",
}


def effective_unit_price(item):
    """Return (value, basis). Only explicit, complete denominators; never allocate a package price."""
    value = unit_price(item.get("price"), item.get("area"), scope="parcel", share=item.get("share"), category=item.get("category"))
    if value is not None:
        return value, "parcel_price"
    if not (item.get("transaction_complete_land") and item.get("transaction_full_share")):
        return None, None
    value = unit_price(item.get("transaction_price"), item.get("transaction_area"),
                       scope="transaction_complete_land", share="1/1", category=item.get("category"))
    if value is None:
        return None, None
    return value, "single_parcel_land_transaction" if item.get("transaction_parcel_count") == 1 else "package_land_transaction"


def stable_id(*parts):
    return hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()


def checksum(payload):
    return stable_id(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


PARCEL_ID = re.compile(r"^\d{6}_[1-9]\.\d{4}\.(?:AR_\d+\.)?\d+(?:/\d+)?$")


def parcel_id(value):
    value = (value or "").strip()
    if not PARCEL_ID.fullmatch(value):
        raise ContractError(f"Nieprawidłowy identyfikator działki: {value[:80]}")
    return value


def sale_date(value):
    if not value:
        return None
    try:
        result = date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ContractError("Nieprawidłowa data dokumentu") from exc
    if result > date.today():
        raise ContractError("Data dokumentu w przyszłości")
    return result.isoformat()


FOLD_FROM = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
FOLD_TO = "acelnoszzacelnoszz"


def fold_text(value):
    return (value or "").translate(str.maketrans(FOLD_FROM, FOLD_TO)).lower()


def land_category(value):
    value = str(value or "").lower().strip()
    # Numeric dictionaries are not guessed.
    if "niezabudowan" in value:
        return "unbuilt"
    if "zabudowan" in value:
        return "built"
    return "unknown"


def distribution(values):
    values = sorted(number(v) for v in values if v is not None)
    if not values:
        return {"count": 0, "median": None, "min": None, "max": None, "histogram": []}
    low, high = values[0], values[-1]
    width = (high-low)/10 if high > low else Decimal(1)
    counts = Counter(min(9, int((v-low)/width)) for v in values)
    return {"count": len(values), "median": money(median(values)), "min": money(low), "max": money(high),
            "histogram": [{"from": money(low+i*width), "to": money(low+(i+1)*width), "count": counts[i]} for i in range(10)]}


def evidence(value, source, updated_at=None, status="confirmed", note=None):
    return {"value": value, "status": status if value is not None else "unavailable", "source": source,
            "updated_at": updated_at, "note": note}
