"""Parcel and transaction cards: one ordered list of labelled rows shared by API, UI, CLI and tests."""
from decimal import Decimal
from .domain import number, effective_unit_price, UNIT_BASIS

MISSING = "Niedostępne"

LABELS = {
    "wolnyRynek": "Wolny rynek", "sprzedazBezprzetargowa": "Sprzedaż bezprzetargowa",
    "sprzedazPrzetargowa": "Sprzedaż przetargowa", "sprzedazWPostepowaniuEgzekucyjnym": "Sprzedaż w postępowaniu egzekucyjnym",
    "sprzedazNaCelPubliczny": "Sprzedaż na cel publiczny", "sprzedazZBonifikata": "Sprzedaż z bonifikatą",
    "rynekPierwotny": "Rynek pierwotny", "rynekWtorny": "Rynek wtórny",
    "wlasnoscNieruchomosciGruntowej": "Własność nieruchomości gruntowej", "uzytkowanieWieczyste": "Użytkowanie wieczyste",
    "wlasnoscLokaluWrazZPrawemZwiazanym": "Własność lokalu z prawem związanym",
    "wlasnoscBudynkuWrazZPrawemZwiazanym": "Własność budynku z prawem związanym",
    "skarbPanstwa": "Skarb Państwa", "jednostkaSamorzaduTerytorialnego": "Jednostka samorządu terytorialnego",
    "osobaFizyczna": "Osoba fizyczna", "osobaPrawna": "Osoba prawna",
    "nieruchomoscGruntowaNiezabudowana": "Gruntowa niezabudowana", "nieruchomoscGruntowaZabudowana": "Gruntowa zabudowana",
    "nieruchomoscBudynkowa": "Budynkowa", "nieruchomoscLokalowa": "Lokalowa",
    "gruntyRolne": "Grunty rolne", "gruntyLesne": "Grunty leśne", "gruntyZabudowaneIZurbanizowane": "Grunty zabudowane i zurbanizowane",
    "terenyKomunikacyjne": "Tereny komunikacyjne", "inne": "Inne",
    "brakMPZPLubWZ": "Brak MPZP lub decyzji WZ", "budownictwoMieszkanioweJednorodzinne": "MN — zabudowa mieszkaniowa jednorodzinna",
    "budownictwoMieszkanioweWielorodzinne": "MW — zabudowa mieszkaniowa wielorodzinna", "terenZabudowyUslugowej": "U — zabudowa usługowa",
    "terenSportuIRekreacji": "US — sport i rekreacja", "terenRozmieszczeniaDuzychObiektowHandlowych": "UC — duże obiekty handlowe",
    "terenRolniczy": "R — teren rolniczy", "terenObslugiProdukcjiWGospodarstwachRolnych": "RU — obsługa produkcji rolnej",
    "terenZabudowyZagrodowejGospodarstwRolnych": "RM — zabudowa zagrodowa", "terenObiektowProdukcyjnychSkladowIMagazynow": "P — produkcja, składy, magazyny",
    "obszarITerenGorniczy": "PG — teren górniczy", "terenZieleniObjetyFormaOchronyPrzyrody": "ZN — zieleń chroniona",
    "las": "ZL — las", "terenZieleniUrzadzonej": "ZP — zieleń urządzona", "terenOgrodowDzialkowych": "ZD — ogrody działkowe",
    "cmentarz": "ZC — cmentarz", "terenWodPowierzchniowychMorskich": "WM — wody morskie",
    "terenWodPowierzchniowychSrodladowych": "WS — wody śródlądowe", "terenDrogPublicznych": "KD — drogi publiczne",
    "terenDrogWewnetrznych": "KDW — drogi wewnętrzne", "terenKomunikacjiWodnejSzlakWodny": "KW — komunikacja wodna",
    "terenInfrastrukturyTechnicznej": "TIT — infrastruktura techniczna", "innyNiewymieniony": "INN — inne przeznaczenie",
    "dezycjaWarunkiZabudowy": "WZ — decyzja o warunkach zabudowy",
    "przemyslowy": "Przemysłowy", "transportuILacznosci": "Transportu i łączności", "handlowoUslugowy": "Handlowo-usługowy",
    "zbiornikiSilosyMagazyny": "Zbiorniki, silosy, magazyny", "biurowy": "Biurowy", "szpitale": "Szpital / opieka",
    "oswiatyISportu": "Oświaty i sportu", "gospodarczy": "Gospodarczy", "pozostaleNiemieszkalne": "Pozostały niemieszkalny",
    "mieszkalny": "Mieszkalny", "mieszkalna": "Mieszkalna", "handlowoUslugowa": "Handlowo-usługowa", "biurowa": "Biurowa",
    "produkcyjna": "Produkcyjna", "garaz": "Garaż", "inna": "Inna",
}
CATEGORY = {"unbuilt": "Niezabudowana", "built": "Zabudowana", "unknown": "Nieustalona (lokal, budynek lub brak kodu)"}
ISSUES = {
    "geometry_missing": "RCN nie podaje geometrii", "invalid_geometry": "Nieprawidłowa geometria w RCN",
    "area_missing": "Brak powierzchni", "area_unit_unavailable": "Brak jednostki powierzchni",
    "price_missing": "Brak ceny", "date_missing": "Brak daty", "property_price_nonpositive": "Cena nieruchomości w RCN ≤ 0",
    "price_nonpositive": "Cena działki ≤ 0", "total_nonpositive": "Cena aktu ≤ 0", "area_nonpositive": "Powierzchnia ≤ 0",
    "property_area_nonpositive": "Powierzchnia nieruchomości ≤ 0",
}
COUNTIES = {"0801": "gorzowski"}
VOIVODESHIPS = {"08": "lubuskie"}


SMALL_WORDS = {"nad", "pod", "w", "i", "przy", "na", "z", "ze", "do", "od"}


def place_name(value):
    """RCN stores names in capitals ('KOSTRZYN NAD ODRĄ'); show them as written on signs."""
    if not value:
        return None
    words = value.strip().lower().split()
    return " ".join(w if i and w in SMALL_WORDS else "-".join(p[:1].upper() + p[1:] for p in w.split("-")) for i, w in enumerate(words))


def _grouped(value, places):
    text = f"{value:,.{places}f}".replace(",", " ").replace(".", ",")
    return text


ARE = Decimal(100)


def _ares_word(ares):
    shown = ares.quantize(Decimal("0.01"))
    if shown != shown.to_integral_value():
        return "ara"
    n = abs(int(shown))
    n100, n10 = n % 100, n % 10
    if n10 == 1 and n100 != 11:
        return "ar"
    if n10 in (2, 3, 4) and n100 not in (12, 13, 14):
        return "ary"
    return "arów"


def money(value):
    value = number(value)
    return None if value is None else _grouped(value, 2) + " zł"


def area(value):
    """Land area in ares (1 ar = 100 m²)."""
    value = number(value)
    if value is None:
        return None
    ares = value / ARE
    text = _grouped(ares, 2)
    if text.endswith(",00"):
        text = text[:-3]
    return f"{text} {_ares_word(ares)}"


def floor_area(value):
    """Building or premises usable area stays in square metres."""
    value = number(value)
    if value is None:
        return None
    text = _grouped(value, 2)
    return (text[:-3] if text.endswith(",00") else text) + " m²"


def unit(value):
    """Unit price in zł/ar, from a stored zł/m² value."""
    value = number(value)
    return None if value is None else _grouped(value * ARE, 2) + " zł/ar"


def party(item):
    tx = ((item or {}).get("details") or {}).get("transaction") or {}
    return label(tx.get("seller_type")), label(tx.get("buyer_type"))


def label(value):
    return None if value is None else LABELS.get(value, value)


def yes_no(value):
    return None if value is None else ("Tak" if value else "Nie")


def row(key, title, value, status="confirmed", source=None, note=None, link=None, sub=None):
    value = None if value in ("", [], None) else value
    result = {"key": key, "label": title, "value": value if value is not None else MISSING,
              "status": status if value is not None else "unavailable", "source": source if value is not None else None}
    if note:
        result["note"] = note
    if link:
        result["link"] = link
    if sub:
        result["sub"] = sub
    return result


def section(key, title, rows):
    return {"key": key, "title": title, "rows": rows}


def observation_sections(prefix, item, sale, rcn):
    details = item.get("details") or {}
    tx, prop, parcel = details.get("transaction") or {}, details.get("property") or {}, details.get("parcel") or {}
    value, basis = effective_unit_price(item)
    sections = [section(prefix + ".transaction", "Transakcja (cały akt)", [
        row(prefix + ".transaction.date", "Data aktu", sale.get("sale_date") and str(sale["sale_date"]), source=rcn),
        row(prefix + ".transaction.price", "Cena całego aktu brutto", money(sale.get("price")), source=rcn,
            note="Cena aktu, nie cena pojedynczej działki."),
        row(prefix + ".transaction.vat", "VAT w cenie aktu", money(tx.get("vat")), source=rcn),
        row(prefix + ".transaction.kind", "Rodzaj transakcji", label(item.get("transaction_type")), source=rcn),
        row(prefix + ".transaction.market", "Rynek", label(item.get("market")), source=rcn),
        row(prefix + ".transaction.seller", "Strona sprzedająca (rodzaj)", label(tx.get("seller_type")), source=rcn),
        row(prefix + ".transaction.buyer", "Strona kupująca (rodzaj)", label(tx.get("buyer_type")), source=rcn),
        row(prefix + ".transaction.designation", "Oznaczenie transakcji w RCN", tx.get("designation"), source=rcn),
        row(prefix + ".transaction.document", "Oznaczenie dokumentu", tx.get("document"), source=rcn),
        row(prefix + ".transaction.properties", "Nieruchomości w akcie", item.get("transaction_property_count") and str(item["transaction_property_count"]), source=rcn),
        row(prefix + ".transaction.parcels", "Działki w akcie", item.get("transaction_parcel_count") and str(item["transaction_parcel_count"]), source=rcn),
        row(prefix + ".transaction.complete_land", "Akt obejmuje wyłącznie grunt w całości", yes_no(item.get("transaction_complete_land")),
            status="inferred", source="wyliczone z relacji RCN"),
        row(prefix + ".transaction.land_area", "Powierzchnia wszystkich działek aktu", area(item.get("transaction_area")),
            status="inferred", source="suma powierzchni RCN"),
        row(prefix + ".transaction.iip", "Identyfikator IIP", item.get("namespace") and f"{item['namespace']}/{item.get('transaction_source_id')}", source=rcn),
        row(prefix + ".transaction.version", "Wersja rekordu", item.get("source_version"), source=rcn),
    ])]
    related = [pid for pid in tx.get("parcel_ids") or [] if pid != item.get("parcel_id")]
    if related:
        sections.append(section(prefix + ".related", "Inne działki w tym akcie",
                                [row(f"{prefix}.related.{i}", f"Działka {i + 1}", pid, source=rcn, link=pid) for i, pid in enumerate(related)]))
    sections.append(section(prefix + ".parcel", "Ta działka w akcie", [
        row(prefix + ".parcel.price", "Cena tej działki brutto", money(item.get("price")), source=rcn,
            note=None if item.get("price") else "RCN nie podaje osobnej ceny tej działki."),
        row(prefix + ".parcel.vat", "VAT w cenie działki", money(parcel.get("vat")), source=rcn),
        row(prefix + ".parcel.area", "Powierzchnia ewidencyjna", area(item.get("area")), source=rcn),
        row(prefix + ".parcel.unit_price", "Cena za ar", unit(value), status="inferred", source="z ceny i powierzchni RCN",
            note=UNIT_BASIS[basis] if basis else "Brak uzasadnionego mianownika: pakiet z budynkiem/lokalem, udział niepełny lub brak ceny."),
        row(prefix + ".parcel.category", "Kategoria gruntu", CATEGORY.get(item.get("category")), status="inferred", source="z rodzaju nieruchomości RCN"),
        row(prefix + ".parcel.land_use", "Sposób użytkowania", label(item.get("land_use")), source=rcn),
        row(prefix + ".parcel.plan", "Przeznaczenie w MPZP w dniu sprzedaży", label(item.get("plan_at_sale")), source=rcn,
            note="Stan zapisany w RCN przy sprzedaży, nie aktualny plan."),
        row(prefix + ".parcel.addresses", "Adresy działki", "; ".join(parcel.get("addresses") or []) or item.get("address"), source=rcn),
        row(prefix + ".parcel.info", "Dodatkowe informacje (tekst RCN)", parcel.get("info"), source=rcn),
        row(prefix + ".parcel.geometry", "Geometria w RCN", {"rcn_parcel_boundary": "Obrys działki z pliku RCN", "approximate_transaction": "Przybliżona lokalizacja"}.get(item.get("geometry_kind")),
            source=rcn),
        row(prefix + ".parcel.issues", "Uwagi jakości", ", ".join(ISSUES.get(i, i) for i in item.get("issues") or []) or "Brak", status="inferred", source="kontrola importu"),
    ]))
    sections.append(section(prefix + ".property", "Nieruchomość, do której należy działka", [
        row(prefix + ".property.kind", "Rodzaj nieruchomości", label(item.get("category_raw")), source=rcn),
        row(prefix + ".property.right", "Prawo", label(item.get("right")), source=rcn),
        row(prefix + ".property.share", "Udział w prawie", item.get("share"), source=rcn),
        row(prefix + ".property.land_area", "Pole gruntu nieruchomości", area(item.get("property_area")), source=rcn),
        row(prefix + ".property.price", "Cena nieruchomości brutto", money(item.get("property_price")), source=rcn),
        row(prefix + ".property.vat", "VAT w cenie nieruchomości", money(prop.get("vat")), source=rcn),
        row(prefix + ".property.description", "Opis nieruchomości (tekst RCN)", prop.get("description"), source=rcn),
        row(prefix + ".property.parcels", "Działki tej nieruchomości", ", ".join(prop.get("parcel_ids") or []), source=rcn),
    ]))
    for i, b in enumerate(prop.get("buildings") or []):
        sections.append(section(f"{prefix}.building.{i}", f"Budynek {i + 1}", [
            row(f"{prefix}.building.{i}.id", "Identyfikator budynku", b.get("id"), source=rcn),
            row(f"{prefix}.building.{i}.kind", "Rodzaj budynku", label(b.get("kind")), source=rcn),
            row(f"{prefix}.building.{i}.area", "Powierzchnia użytkowa", floor_area(b.get("usable_area")), source=rcn),
            row(f"{prefix}.building.{i}.price", "Cena budynku brutto", money(b.get("price")), source=rcn),
            row(f"{prefix}.building.{i}.vat", "VAT", money(b.get("vat")), source=rcn),
            row(f"{prefix}.building.{i}.addresses", "Adres budynku", "; ".join(b.get("addresses") or []), source=rcn),
            row(f"{prefix}.building.{i}.info", "Dodatkowe informacje (tekst RCN)", b.get("info"), source=rcn),
        ]))
    for i, u in enumerate(prop.get("premises") or []):
        sections.append(section(f"{prefix}.premises.{i}", f"Lokal {i + 1}", [
            row(f"{prefix}.premises.{i}.id", "Identyfikator lokalu", u.get("id"), source=rcn),
            row(f"{prefix}.premises.{i}.function", "Funkcja", label(u.get("function")), source=rcn),
            row(f"{prefix}.premises.{i}.rooms", "Liczba izb", u.get("rooms"), source=rcn),
            row(f"{prefix}.premises.{i}.floor", "Kondygnacja", u.get("floor"), source=rcn),
            row(f"{prefix}.premises.{i}.area", "Powierzchnia użytkowa", floor_area(u.get("usable_area")), source=rcn),
            row(f"{prefix}.premises.{i}.auxiliary", "Pomieszczenia przynależne", floor_area(u.get("auxiliary_area")), source=rcn),
            row(f"{prefix}.premises.{i}.price", "Cena lokalu brutto", money(u.get("price")), source=rcn),
            row(f"{prefix}.premises.{i}.vat", "VAT", money(u.get("vat")), source=rcn),
            row(f"{prefix}.premises.{i}.addresses", "Adres budynku z lokalem", "; ".join(u.get("addresses") or []), source=rcn),
            row(f"{prefix}.premises.{i}.info", "Dodatkowe informacje (tekst RCN)", u.get("info"), source=rcn),
        ]))
    return sections


def parcel_sections(parcel, latest, sales, address, favorite, imported):
    pid = parcel["id"]
    teryt = pid.split("_")[0]
    county, voivodeship = teryt[:4], teryt[:2]
    uldk = "ULDK" if parcel.get("geometry") else None
    rcn = "RCN"
    no_context = "Brak zweryfikowanej usługi dla tej działki. Nie oznacza braku ograniczeń."
    rows_parcel = [
        row("parcel.id", "Identyfikator działki", pid),
        row("parcel.number", "Numer działki", parcel.get("number") or pid.rsplit(".", 1)[-1]),
        row("parcel.precinct_code", "Kod obrębu", pid.split(".")[1] if "." in pid else None, source="identyfikator"),
        row("parcel.region", "Obręb", parcel.get("region"), source=uldk),
        row("parcel.commune", "Gmina", parcel.get("commune"), source=uldk),
        row("parcel.county", "Powiat", COUNTIES.get(county) and f"{COUNTIES[county]} ({county})", status="inferred", source="kod TERYT"),
        row("parcel.voivodeship", "Województwo", VOIVODESHIPS.get(voivodeship) and f"{VOIVODESHIPS[voivodeship]} ({voivodeship})", status="inferred", source="kod TERYT"),
        row("parcel.address_point", "Adres (punkt adresowy GUGiK)", address and address.get("label"), source="GUGiK UUG",
            note=address and "Działka wskazana przez punkt adresowy; budynek może stać na sąsiedniej działce tej samej posesji."),
        row("parcel.addresses_rcn", "Adresy działki w RCN", latest and ("; ".join((latest.get("details") or {}).get("parcel", {}).get("addresses") or []) or latest.get("address")), source=rcn),
        row("parcel.owner", "Aktualny właściciel", party(latest)[1], source=rcn,
            note="Strona kupująca ostatniej transakcji w RCN (rodzaj, nie dane osobowe). Imion i nazwisk rejestr nie publikuje."),
        row("parcel.area", "Powierzchnia ewidencyjna (ostatnia sprzedaż)", latest and area(latest.get("area")), source=rcn),
        row("parcel.land_use", "Sposób użytkowania (ostatnia sprzedaż)", latest and label(latest.get("land_use")), source=rcn),
        row("parcel.label", "Moja etykieta", favorite, source="użytkownik"),
    ]
    rows_geometry = [
        row("geometry.kind", "Rodzaj granicy na mapie", "Granica ULDK (stan bieżący)" if parcel.get("geometry") else
            ("Obrys działki z pliku RCN (stan z dnia sprzedaży)" if parcel.get("rcn_geometry") else None),
            source=uldk or rcn),
        row("geometry.source", "Źródło granicy", parcel.get("geometry_source") or (parcel.get("rcn_geometry") and "RCN powiatu gorzowskiego"), source=uldk or rcn),
        row("geometry.upstream", "Usługa źródłowa ULDK", parcel.get("upstream_source"), source=uldk),
        row("geometry.fetched_at", "Granica pobrana", parcel.get("geometry_fetched_at") and str(parcel["geometry_fetched_at"])[:19].replace("T", " ") + " UTC", source=uldk),
        row("geometry.area", "Powierzchnia z geometrii", area(parcel.get("geometry_area") and Decimal(str(round(parcel["geometry_area"], 2)))),
            status="inferred", source="obliczone z geometrii", note="Pole geodezyjne z obrysu; urzędowa jest powierzchnia ewidencyjna."),
        row("geometry.center", "Środek działki (szer., dł.)", parcel.get("center") and f"{parcel['center'][1]:.6f}, {parcel['center'][0]:.6f}",
            status="inferred", source="obliczone z geometrii"),
    ]
    last = sales[0] if sales else None
    rows_history = [
        row("history.count", "Sprzedaże w RCN", str(len(sales)), source=rcn,
            note="Brak sprzedaży w bazie nie oznacza, że działki nigdy nie sprzedano."),
        row("history.last_date", "Ostatnia sprzedaż", last and last.get("sale_date") and str(last["sale_date"]), source=rcn),
        row("history.last_price", "Cena ostatniego aktu", last and money(last.get("price")), source=rcn, note="Cena całego aktu."),
    ]
    rows_context = [
        row("context.plan_at_sale", "MPZP przy ostatniej sprzedaży", latest and label(latest.get("plan_at_sale")), source=rcn),
        row("context.current_plan", "Aktualne MPZP", None, note=no_context),
        row("context.utilities", "Uzbrojenie (GESUT)", None, note=no_context),
        row("context.flood", "Zagrożenie powodziowe (ISOK)", None, note=no_context),
        row("context.nature", "Ochrona przyrody (GDOŚ)", None, note=no_context),
        row("context.terrain", "Rzeźba terenu (NMT)", None, note=no_context),
    ]
    rows_sources = [
        row("sources.rcn_snapshot", "Plik RCN — stan na", imported and imported.get("snapshot"), source=rcn),
        row("sources.rcn_file", "Plik RCN — adres", imported and imported.get("download_url"), source=rcn),
        row("sources.rcn_imported", "Import do bazy", imported and imported.get("finished_at") and str(imported["finished_at"])[:19] + " UTC", source="LandScope"),
    ]
    return [section("parcel", "Działka", rows_parcel), section("geometry", "Granica i położenie", rows_geometry),
            section("history", "Historia sprzedaży", rows_history), section("context", "Otoczenie i ograniczenia", rows_context),
            section("sources", "Źródła i aktualność", rows_sources)]


def summary_sections(observations, trend, precinct):
    """Headline tiles, the sale list and the precinct trend; observations are newest first."""
    latest = observations[0] if observations else None
    unit_value, basis = effective_unit_price(latest["payload"]) if latest else (None, None)
    rcn = "RCN"
    tiles = [
        row("summary.last_price", "Ostatnia cena aktu", latest and money(latest["price"]), source=rcn,
            sub=latest and latest.get("sale_date") and str(latest["sale_date"])),
        row("summary.unit_price", "Cena za ar", unit(unit_value), status="inferred", source="z ceny i powierzchni RCN",
            note=UNIT_BASIS.get(basis) if basis else None),
        row("summary.area", "Pow. działki", latest and area(latest["payload"].get("area")), source=rcn),
        row("summary.sales", "Sprzedaże w RCN", str(len({o["sale_id"] for o in observations})), source=rcn),
    ]
    sales, owners, seen = [], [], set()
    for o in observations:
        if o["sale_id"] in seen:
            continue
        seen.add(o["sale_id"])
        value, _ = effective_unit_price(o["payload"])
        sales.append(row(f"transactions.{len(sales)}", str(o["sale_date"] or "Brak daty"),
                         " · ".join(filter(None, [money(o["price"]) or MISSING, unit(value)])), source=rcn,
                         note=label(o["payload"].get("market"))))
        seller, buyer = party(o["payload"])
        owners.append(row(f"owners.{len(owners)}", str(o["sale_date"] or "Brak daty"),
                          f"{seller or MISSING} → {buyer or MISSING}", source=rcn,
                          note="Rodzaj strony umowy z RCN, nie imię i nazwisko."))
    trend_rows = [row(f"trend.{t['year']}", str(t["year"]), f"{unit(Decimal(str(t['median'])))} · {t['n']} " + ("akt" if t["n"] == 1 else "akty" if t["n"] % 10 in (2, 3, 4) and t["n"] % 100 not in (12, 13, 14) else "aktów"),
                      status="inferred", source="mediana z RCN") for t in trend]
    result = [section("summary", "Podsumowanie", tiles)]
    if sales:
        result.append(section("transactions", f"Transakcje ({len(sales)})", sales))
        result.append(section("owners", "Właściciele (od kogo → do kogo)", owners))
    result.append(section("trend", f"Mediana ceny za ar działek niezabudowanych w obrębie {precinct}",
                           trend_rows or [row("trend.none", "Brak danych", None, note="W obrębie nie ma sprzedaży pojedynczej działki gruntu z ceną za ar.")]))
    return result


def flat_rows(card):
    for sec in card.get("sections", []):
        for r in sec["rows"]:
            yield sec, r
    for sale in card.get("sales", []):
        for sec in sale["sections"]:
            for r in sec["rows"]:
                yield sec, r
