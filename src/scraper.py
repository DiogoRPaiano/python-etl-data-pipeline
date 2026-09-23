"""Retrieve GeoJSON earthquake events from the USGS catalog."""

from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
MAX_EVENTS = 20_000


def fetch_earthquakes(
    start_date: date,
    end_date: date,
    min_magnitude: float = 4.5,
    session: requests.Session | None = None,
) -> list[dict]:
    """Fetch events for an inclusive UTC date range."""
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")

    owns_session = session is None
    if session is None:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))

    try:
        response = session.get(
            API_URL,
            params={
                "format": "geojson",
                "starttime": start_date.isoformat(),
                "endtime": f"{end_date.isoformat()}T23:59:59.999",
                "minmagnitude": min_magnitude,
                "eventtype": "earthquake",
                "limit": MAX_EVENTS,
            },
            timeout=(5, 30),
        )
        if response.status_code == 204:
            return []
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ValueError("USGS response is missing a GeoJSON features array")
        features = payload["features"]
        if len(features) >= MAX_EVENTS:
            raise ValueError("USGS result reached 20,000 events; use a shorter date range")
        return features
    finally:
        if owns_session:
            session.close()
