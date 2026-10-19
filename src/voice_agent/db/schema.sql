CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS listings (
    listing_id         text PRIMARY KEY,
    model_id           text NOT NULL,
    make               text NOT NULL,
    model              text NOT NULL,
    variant            text NOT NULL,
    body_type          text NOT NULL,
    fuel               text NOT NULL,
    year               int  NOT NULL,
    price_inr          int  NOT NULL,
    km_driven          int  NOT NULL,
    payload_kg         int  NOT NULL,
    gvw_kg             int  NOT NULL,
    city               text NOT NULL,
    registration_state text NOT NULL,
    owners             int  NOT NULL,
    seller_type        text NOT NULL,
    papers_verified    boolean NOT NULL,
    listing_date       date NOT NULL,
    description        text NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_filter_idx ON listings (body_type, fuel, city, price_inr);

CREATE TABLE IF NOT EXISTS aliases (
    alias     text NOT NULL,
    canonical text NOT NULL,
    kind      text NOT NULL,
    PRIMARY KEY (alias, kind)
);
CREATE INDEX IF NOT EXISTS aliases_trgm_idx ON aliases USING gin (alias gin_trgm_ops);

CREATE TABLE IF NOT EXISTS city_neighbors (
    city        text NOT NULL,
    neighbor    text NOT NULL,
    distance_km int  NOT NULL,
    PRIMARY KEY (city, neighbor)
);

CREATE TABLE IF NOT EXISTS turn_log (
    id         bigserial PRIMARY KEY,
    session_id text NOT NULL,
    turn       int  NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    record     jsonb NOT NULL
);
