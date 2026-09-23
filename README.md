# Python ETL Pipeline & SQL Storage

A Python ETL pipeline that collects earthquake events from the [USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/), validates and cleans GeoJSON with pandas, and stores the results in PostgreSQL. SQLite is supported for a quick local run.

## Architecture

![Extract, transform, and load architecture](docs/architecture-diagram.png)

The [editable diagram](docs/architecture-diagram.drawio) opens in diagrams.net.

1. **Extract:** `requests` calls the USGS catalog with a date range and minimum magnitude. HTTP retries handle transient failures.
2. **Transform:** `pandas` converts epoch milliseconds to UTC timestamps, checks required fields and geographic ranges, and fills missing place names. Invalid records are logged and skipped.
3. **Load:** SQLAlchemy writes batches in a transaction. An upsert on the USGS event ID updates records only when the source has a newer version, so rerunning a date range is safe.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --database-url sqlite:///earthquakes.db
```

The default query covers the previous seven complete UTC days and magnitude 4.5 or above. The database table is created automatically. To query a specific interval (both dates inclusive):

```bash
python -m src.main --start-date 2026-09-01 --end-date 2026-09-07 --min-magnitude 5.0 --database-url sqlite:///earthquakes.db
```

For PostgreSQL, create an empty database, set `DATABASE_URL`, and run the same command. The schema is created automatically; [`sql/schema.sql`](sql/schema.sql) is also provided for manual setup or review.

```bash
# Example; replace credentials and host with your own values.
export DATABASE_URL='postgresql+psycopg://etl_user:password@localhost:5432/earthquakes'
python -m src.main
```

In PowerShell, set the variable with `$env:DATABASE_URL = 'postgresql+psycopg://...'`. Avoid committing credentials; the sample environment file is [`.env.example`](.env.example). The application reads `DATABASE_URL` from the process environment, not from `.env` automatically.

Example inspection query:

```sql
SELECT event_id, occurred_at, magnitude, place
FROM earthquakes
ORDER BY occurred_at DESC
LIMIT 10;
```

## Project structure

```text
docs/architecture-diagram.drawio  Editable diagrams.net source
docs/architecture-diagram.png     README preview
src/scraper.py                     USGS API client
src/transformer.py                 pandas cleaning and validation
src/database.py                    SQLAlchemy schema and batch upsert
src/main.py                        CLI and pipeline orchestration
sql/schema.sql                     PostgreSQL DDL
tests/                             Offline transformation and load tests
.github/workflows/tests.yml        GitHub Actions test matrix
```

## Data contract and reliability

The source is the [USGS GeoJSON query API](https://earthquake.usgs.gov/fdsnws/event/1/) and the [GeoJSON field specification](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php). The pipeline stores the event ID, origin and update timestamps in UTC, magnitude, place, longitude, latitude, depth in kilometers, and source URL. Events without a valid ID, time, magnitude, or coordinates are skipped with a warning. Missing place names become `Unknown location`; missing depth remains `NULL`.

The API limits a query to 20,000 events. The pipeline fails clearly if the response reaches that limit; split large backfills into smaller date ranges. A USGS no-data (HTTP 204) response produces a successful run with zero rows. Source data can be revised later, so rerun recent intervals to pick up updates. This project does not handle deleted events.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests use fixtures and an in-memory SQLite database; they do not need network access or PostgreSQL.
GitHub Actions runs the same suite on Python 3.11 and 3.12.

## License

MIT. USGS earthquake data is provided by the U.S. Geological Survey; follow its [data policies](https://www.usgs.gov/information-policies-and-instructions/usgs-data-policies) when reusing it.
