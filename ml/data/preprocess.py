from __future__ import annotations

from typing import Any, Optional, TypedDict


# Shared schema — every data source must be mapped to this before entering the ML pipeline.
# WIP Mapping of features from different sources to these fields
class PlaceRecord(TypedDict, total=False):
    place_id:      str
    name:          str
    source:        str            # "geoapify" | "yelp" | "google" | "lim_poi"
    latitude:      float
    longitude:     float
    city:          Optional[str]
    state:         Optional[str]
    country:       Optional[str]
    postcode:      Optional[str]
    street:        Optional[str]
    suburb:        Optional[str]
    district:      Optional[str]
    # lowercase, e.g. ["catering.restaurant"] or ["restaurants", "italian"]
    categories:    list[str]
    price_level:   Optional[int]  # 1–4
    rating:        Optional[float]
    review_count:  Optional[int]
    hours:         Optional[str]
    # Yelp-style extras (GoodForKids, DogsAllowed, etc.)
    attributes:    Optional[dict[str, Any]]
    tags:          Optional[list[str]]       # filled in by Stage 1 classifier
