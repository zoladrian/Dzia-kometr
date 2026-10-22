CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS schema_version (version integer PRIMARY KEY, installed_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS import_run (
 id text PRIMARY KEY, source text NOT NULL, county text NOT NULL, status text NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, report jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS sale (
 id text PRIMARY KEY, namespace text NOT NULL, source_id text NOT NULL,
 sale_date date, price numeric, source_version text,
 UNIQUE(namespace,source_id)
);
CREATE TABLE IF NOT EXISTS property (
 id text PRIMARY KEY, sale_id text NOT NULL REFERENCES sale(id),
 source_id text, identity_status text NOT NULL, price numeric, area numeric, category text NOT NULL,
 share text, right_type text, CHECK(identity_status IN ('confirmed','unavailable'))
);
CREATE TABLE IF NOT EXISTS parcel (
 id text PRIMARY KEY, commune text, region text, number text,
 boundary geometry(MultiPolygon,4326), geometry_source text, geometry_fetched_at timestamptz,
 upstream_source text, CHECK(boundary IS NULL OR ST_IsValid(boundary))
);
CREATE TABLE IF NOT EXISTS observation (
 id text PRIMARY KEY, sale_id text NOT NULL REFERENCES sale(id),
 property_id text NOT NULL REFERENCES property(id), parcel_id text NOT NULL REFERENCES parcel(id),
 county text NOT NULL, feature_id text NOT NULL, source text NOT NULL,
 price numeric, area numeric, category text NOT NULL, address text, land_use text,
 location geometry(Geometry,4326), payload jsonb NOT NULL, hash text NOT NULL,
 run_id text NOT NULL REFERENCES import_run(id), fetched_at timestamptz NOT NULL DEFAULT now(),
 active boolean NOT NULL DEFAULT true, UNIQUE(source,feature_id),
 CHECK(location IS NULL OR ST_IsValid(location))
);
CREATE TABLE IF NOT EXISTS raw_record (
 id bigserial PRIMARY KEY, observation_id text NOT NULL, hash text NOT NULL, run_id text NOT NULL REFERENCES import_run(id),
 source_url text NOT NULL, fetched_at timestamptz NOT NULL DEFAULT now(), payload jsonb NOT NULL,
 UNIQUE(observation_id,hash)
);
CREATE TABLE IF NOT EXISTS rejected_record (
 id bigserial PRIMARY KEY, run_id text NOT NULL REFERENCES import_run(id), feature_id text, reason text NOT NULL,
 raw jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS favorite (
 parcel_id text PRIMARY KEY REFERENCES parcel(id), label text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS enrichment (
 parcel_id text NOT NULL REFERENCES parcel(id), source text NOT NULL, payload jsonb NOT NULL,
 fetched_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(parcel_id,source)
);
ALTER TABLE observation ADD COLUMN IF NOT EXISTS unit_price numeric;
ALTER TABLE observation ADD COLUMN IF NOT EXISTS unit_basis text;
CREATE INDEX IF NOT EXISTS observation_location_idx ON observation USING gist(location);
CREATE INDEX IF NOT EXISTS observation_unit_idx ON observation(unit_price) WHERE unit_price IS NOT NULL;
CREATE INDEX IF NOT EXISTS parcel_boundary_idx ON parcel USING gist(boundary);
CREATE INDEX IF NOT EXISTS observation_sale_idx ON observation(sale_id);
CREATE INDEX IF NOT EXISTS observation_parcel_idx ON observation(parcel_id);
CREATE INDEX IF NOT EXISTS observation_county_idx ON observation(county,active);
CREATE INDEX IF NOT EXISTS sale_date_idx ON sale(sale_date);
CREATE TABLE IF NOT EXISTS app_setting (
 key text PRIMARY KEY, value jsonb NOT NULL
);
INSERT INTO schema_version(version) VALUES (1) ON CONFLICT DO NOTHING;
