"""Offline checks for extraction, transformation, and idempotent loading."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from src.database import earthquakes, open_database, upsert_earthquakes
from src.scraper import MAX_EVENTS, fetch_earthquakes
from src.transformer import transform_earthquakes


@pytest.fixture
def event():
    return {
        "id": "us-test-1",
        "properties": {
            "time": 1_725_148_800_000,
            "updated": 1_725_149_000_000,
            "mag": 5.2,
            "place": None,
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us-test-1",
        },
        "geometry": {"type": "Point", "coordinates": [-72.5, -18.2, 35.0]},
    }


def test_transform_cleans_and_rejects_invalid_records(event, caplog):
    no_coordinates = deepcopy(event)
    no_coordinates["id"] = "bad-coordinates"
    no_coordinates["geometry"]["coordinates"] = [200, 0, 1]
    no_time = deepcopy(event)
    no_time["id"] = "bad-time"
    no_time["properties"]["time"] = None
    newer = deepcopy(event)
    newer["properties"]["updated"] += 1_000
    newer["properties"]["mag"] = 5.3

    result = transform_earthquakes([event, no_coordinates, no_time, newer])

    assert result.rejected == 2
    assert result.duplicates == 1
    assert len(result.rows) == 1
    assert result.rows[0]["place"] == "Unknown location"
    assert result.rows[0]["magnitude"] == 5.3
    assert result.rows[0]["occurred_at"].tzinfo is not None
    assert "bad-coordinates" in caplog.text
    assert "bad-time" in caplog.text


def test_upsert_keeps_newest_version_and_is_idempotent(event):
    engine = open_database("sqlite:///:memory:")
    first = transform_earthquakes([event]).rows
    newer_event = deepcopy(event)
    newer_event["properties"]["updated"] += 10_000
    newer_event["properties"]["mag"] = 6.1
    newer = transform_earthquakes([newer_event]).rows

    assert upsert_earthquakes(engine, first) == 1
    assert upsert_earthquakes(engine, newer) == 1
    assert upsert_earthquakes(engine, first) == 1
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(earthquakes)) == 1
        assert connection.scalar(select(earthquakes.c.magnitude)) == 6.1
    engine.dispose()


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.params = None

    def get(self, url, params, timeout):
        self.params = params
        return self.response


def test_fetch_handles_empty_response_and_dates():
    session = FakeSession(FakeResponse(204))
    assert fetch_earthquakes(date(2024, 9, 1), date(2024, 9, 2), session=session) == []
    assert session.params["starttime"] == "2024-09-01"
    assert session.params["endtime"] == "2024-09-02T23:59:59.999"


def test_fetch_rejects_truncated_result(event):
    session = FakeSession(FakeResponse(200, {"features": [event] * MAX_EVENTS}))
    with pytest.raises(ValueError, match="shorter date range"):
        fetch_earthquakes(date(2024, 9, 1), date(2024, 9, 2), session=session)
