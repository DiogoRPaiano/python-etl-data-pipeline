-- PostgreSQL schema. The Python application creates this table automatically.
CREATE TABLE IF NOT EXISTS earthquakes (
    event_id VARCHAR(80) PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    magnitude DOUBLE PRECISION NOT NULL,
    place TEXT NOT NULL,
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    depth_km DOUBLE PRECISION,
    source_url TEXT
);

CREATE INDEX IF NOT EXISTS ix_earthquakes_occurred_at ON earthquakes (occurred_at);
CREATE INDEX IF NOT EXISTS ix_earthquakes_magnitude ON earthquakes (magnitude);
