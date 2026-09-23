"""Command-line entry point for the USGS ETL pipeline."""

import argparse
import logging
import os
from datetime import date, datetime, timedelta, timezone

from .database import open_database, upsert_earthquakes
from .scraper import fetch_earthquakes
from .transformer import transform_earthquakes

LOGGER = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = datetime.now(timezone.utc).date()
    parser = argparse.ArgumentParser(description="Load USGS earthquake events into PostgreSQL or SQLite")
    parser.add_argument("--start-date", type=date.fromisoformat, default=today - timedelta(days=7))
    parser.add_argument("--end-date", type=date.fromisoformat, default=today - timedelta(days=1))
    parser.add_argument("--min-magnitude", type=float, default=4.5)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", "sqlite:///earthquakes.db"))
    args = parser.parse_args(argv)
    if args.start_date > args.end_date:
        parser.error("--start-date must not be after --end-date")
    if not -2 <= args.min_magnitude <= 10:
        parser.error("--min-magnitude must be between -2 and 10")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    LOGGER.info("Fetching USGS events from %s through %s (UTC)", args.start_date, args.end_date)
    try:
        features = fetch_earthquakes(args.start_date, args.end_date, args.min_magnitude)
        result = transform_earthquakes(features)
        engine = open_database(args.database_url)
        try:
            processed = upsert_earthquakes(engine, result.rows)
        finally:
            engine.dispose()
    except Exception:
        LOGGER.exception("Pipeline failed")
        return 1

    LOGGER.info(
        "Pipeline finished: fetched=%s valid=%s rejected=%s duplicate_ids=%s processed=%s",
        len(features), len(result.rows), result.rejected, result.duplicates, processed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
