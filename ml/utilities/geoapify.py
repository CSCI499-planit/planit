from __future__ import annotations

import logging
from typing import Any

from ml.data.preprocess import PlaceRecord

logger = logging.getLogger(__name__)


# Converts one Geoapify GeoJSON Feature into a PlaceRecord.
# Returns None if the feature has no name or coordinates.
def parse_geoapify_feature(feature: dict[str, Any]) -> PlaceRecord | None:
    props = feature.get("properties", {})
    geom  = feature.get("geometry", {})

    name = props.get("name", "").strip()
    if not name:
        return None

    coords = geom.get("coordinates")
    if not coords or len(coords) < 2:
        return None

    lon, lat = coords[0], coords[1]

    categories: list[str] = [c.lower() for c in (props.get("categories") or [])]

    # pull any useful attributes from Geoapify sub-objects into the shared attributes dict
    attrs: dict[str, Any] = {}
    if props.get("catering"):
        c = props["catering"]
        if c.get("outdoor_seating"):
            attrs["OutdoorSeating"] = c["outdoor_seating"]
        if c.get("cuisine"):
            attrs["cuisine"] = c["cuisine"]
        if c.get("diet"):
            attrs["diet"] = c["diet"]
    if props.get("facilities"):
        f = props["facilities"]
        if f.get("dogs"):
            attrs["DogsAllowed"] = f["dogs"]
        if f.get("wheelchair"):
            attrs["WheelchairAccessible"] = f["wheelchair"]
    if props.get("fee"):
        attrs["HasFee"] = props["fee"]

    return {
        "place_id":      props.get("place_id", ""),
        "name":          name,
        "source":        "geoapify",
        "latitude":      float(lat),
        "longitude":     float(lon),
        "city":          props.get("city"),
        "state":         props.get("state"),
        "country":       props.get("country"),
        "postcode":      str(props.get("postcode", "")) or None,
        "street":        props.get("street"),
        "suburb":        props.get("suburb"),
        "district":      props.get("district"),
        "categories":    categories,
        "hours":         props.get("opening_hours"),
        "attributes":    attrs if attrs else None,
        # Geoapify free tier doesn't return rating/price
        "price_level":   None,
        "rating":        None,
        "review_count":  None,
    }


# Parses a full Geoapify FeatureCollection JSON response into a list of PlaceRecords.
def parse_geoapify_response(response: dict[str, Any]) -> list[PlaceRecord]:
    records: list[PlaceRecord] = []
    skipped = 0
    for feat in response.get("features", []):
        record = parse_geoapify_feature(feat)
        if record is not None:
            records.append(record)
        else:
            skipped += 1
    if skipped:
        logger.debug("Skipped %d features (missing name or coords)", skipped)
    return records
