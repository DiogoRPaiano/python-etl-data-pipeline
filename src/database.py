"""SQLAlchemy schema and transactional batch upserts."""

from collections.abc import Sequence

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Index, MetaData, String, Table, Text, create_engine
from sqlalchemy.engine import Engine

metadata = MetaData()
earthquakes = Table(
    "earthquakes",
    metadata,
    Column("event_id", String(80), primary_key=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("magnitude", Float, nullable=False),
    Column("place", Text, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("depth_km", Float),
    Column("source_url", Text),
    CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
)
Index("ix_earthquakes_occurred_at", earthquakes.c.occurred_at)
Index("ix_earthquakes_magnitude", earthquakes.c.magnitude)


def open_database(database_url: str) -> Engine:
    """Connect and create the table if it does not yet exist."""
    engine = create_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name not in {"postgresql", "sqlite"}:
        engine.dispose()
        raise ValueError("Only PostgreSQL and SQLite are supported")
    metadata.create_all(engine)
    return engine


def upsert_earthquakes(engine: Engine, rows: Sequence[dict], batch_size: int = 500) -> int:
    """Write rows atomically in batches, keeping the newest USGS version."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not rows:
        return 0

    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif engine.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError("Only PostgreSQL and SQLite are supported")

    with engine.begin() as connection:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            statement = insert(earthquakes).values(batch)
            excluded = statement.excluded
            statement = statement.on_conflict_do_update(
                index_elements=[earthquakes.c.event_id],
                set_={
                    "occurred_at": excluded.occurred_at,
                    "updated_at": excluded.updated_at,
                    "magnitude": excluded.magnitude,
                    "place": excluded.place,
                    "longitude": excluded.longitude,
                    "latitude": excluded.latitude,
                    "depth_km": excluded.depth_km,
                    "source_url": excluded.source_url,
                },
                where=excluded.updated_at > earthquakes.c.updated_at,
            )
            connection.execute(statement)
    return len(rows)
