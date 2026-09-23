"""Validate and normalize USGS GeoJSON features with pandas."""

import logging
import math
from dataclasses import dataclass

import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransformResult:
    rows: list[dict]
    rejected: int
    duplicates: int


def transform_earthquakes(features: list[dict]) -> TransformResult:
    """Return database-ready rows, rejecting malformed source records."""
    extracted = []
    rejected = 0
    for position, feature in enumerate(features):
        if not isinstance(feature, dict):
            LOGGER.warning("Skipping feature %s: expected object", position)
            rejected += 1
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(properties, dict) or not isinstance(coordinates, list) or len(coordinates) < 2:
            LOGGER.warning("Skipping event %s: missing properties or coordinates", feature.get("id", position))
            rejected += 1
            continue
        extracted.append(
            {
                "event_id": feature.get("id"),
                "occurred_at": properties.get("time"),
                "updated_at": properties.get("updated"),
                "magnitude": properties.get("mag"),
                "place": properties.get("place"),
                "longitude": coordinates[0],
                "latitude": coordinates[1],
                "depth_km": coordinates[2] if len(coordinates) > 2 else None,
                "source_url": properties.get("url"),
            }
        )

    if not extracted:
        return TransformResult([], rejected, 0)

    frame = pd.DataFrame.from_records(extracted)
    for column in ("occurred_at", "updated_at"):
        frame[column] = pd.to_datetime(frame[column], unit="ms", utc=True, errors="coerce")
    for column in ("magnitude", "longitude", "latitude", "depth_km"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["depth_km"] = frame["depth_km"].replace([float("inf"), float("-inf")], float("nan"))

    frame["updated_at"] = frame["updated_at"].fillna(frame["occurred_at"])
    frame["place"] = frame["place"].where(frame["place"].notna(), "Unknown location")
    frame["place"] = frame["place"].astype(str).str.strip().replace("", "Unknown location")

    valid = (
        frame["event_id"].map(lambda value: isinstance(value, str) and 0 < len(value.strip()) <= 80)
        & frame["occurred_at"].notna()
        & frame["magnitude"].map(lambda value: pd.notna(value) and math.isfinite(value))
        & frame["longitude"].between(-180, 180)
        & frame["latitude"].between(-90, 90)
    )
    for index in frame.index[~valid]:
        LOGGER.warning("Skipping event %s: invalid ID, time, magnitude, or coordinates", frame.at[index, "event_id"])
        rejected += 1

    frame = frame.loc[valid].copy()
    if frame.empty:
        return TransformResult([], rejected, 0)

    frame["event_id"] = frame["event_id"].str.strip()
    frame = frame.sort_values("updated_at").drop_duplicates("event_id", keep="last")
    duplicates = int(valid.sum()) - len(frame)
    rows = []
    for row in frame.to_dict("records"):
        rows.append(
            {
                "event_id": row["event_id"],
                "occurred_at": row["occurred_at"].to_pydatetime(),
                "updated_at": row["updated_at"].to_pydatetime(),
                "magnitude": float(row["magnitude"]),
                "place": row["place"],
                "longitude": float(row["longitude"]),
                "latitude": float(row["latitude"]),
                "depth_km": None if pd.isna(row["depth_km"]) else float(row["depth_km"]),
                "source_url": row["source_url"] if isinstance(row["source_url"], str) else None,
            }
        )
    return TransformResult(rows, rejected, duplicates)
