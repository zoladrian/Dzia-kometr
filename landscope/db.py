from contextlib import contextmanager
from pathlib import Path
from .config import database_url


@contextmanager
def connect(url=None):
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url or database_url(), row_factory=dict_row, connect_timeout=5) as connection:
        yield connection


def initialize():
    with connect() as db:
        # Transaction-level lock makes concurrent CLI/app startup safe.
        db.execute("SELECT pg_advisory_xact_lock(8012026)")
        sql = (Path(__file__).parent / "sql/001_initial.sql").read_text(encoding="utf-8")
        schema = db.execute("SELECT current_schema() AS s").fetchone()["s"]
        # Tests use search_path=test_schema,public. CREATE TABLE IF NOT EXISTS would
        # skip into public tables; drop IF NOT EXISTS so DDL lands in the first schema.
        if schema and schema != "public":
            sql = sql.replace("CREATE TABLE IF NOT EXISTS ", "CREATE TABLE ")
            sql = sql.replace("CREATE INDEX IF NOT EXISTS ", "CREATE INDEX ")
        db.execute(sql)
        consolidate_confirmed_properties(db)


def consolidate_confirmed_properties(db):
    """One GML property per (sale, source_id); observation-level IDs were a model bug."""
    dupes = db.execute("""SELECT 1 FROM property
        WHERE identity_status='confirmed' AND coalesce(source_id,'') <> ''
        GROUP BY sale_id, source_id HAVING count(*) > 1 LIMIT 1""").fetchone()
    if not dupes:
        return
    db.execute("""
        CREATE TEMP TABLE _property_canonical ON COMMIT DROP AS
        SELECT sale_id, source_id,
          encode(sha256(convert_to('property' || chr(31) || sale_id || chr(31) || source_id, 'UTF8')), 'hex') AS id
        FROM property
        WHERE identity_status='confirmed' AND coalesce(source_id,'') <> ''
        GROUP BY sale_id, source_id""")
    db.execute("""INSERT INTO property(id,sale_id,source_id,identity_status,price,area,category,share,right_type)
        SELECT c.id, p.sale_id, p.source_id, p.identity_status, p.price, p.area, p.category, p.share, p.right_type
        FROM _property_canonical c
        JOIN LATERAL (
          SELECT * FROM property x
          WHERE x.sale_id=c.sale_id AND x.source_id=c.source_id AND x.identity_status='confirmed'
          LIMIT 1
        ) p ON true
        ON CONFLICT (id) DO NOTHING""")
    db.execute("""UPDATE observation o SET property_id=c.id
        FROM property p JOIN _property_canonical c ON c.sale_id=p.sale_id AND c.source_id=p.source_id
        WHERE o.property_id=p.id AND p.identity_status='confirmed' AND o.property_id <> c.id""")
    db.execute("""DELETE FROM property p
        WHERE NOT EXISTS (SELECT 1 FROM observation o WHERE o.property_id=p.id)""")


def counts():
    with connect() as db:
        return {table:db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                for table in ("sale","property","parcel","observation","raw_record","rejected_record","import_run")}
