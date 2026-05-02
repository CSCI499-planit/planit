from __future__ import annotations

import logging
from typing import Any, Optional, TypedDict

logger = logging.getLogger(__name__)


class PlaceRecord(TypedDict, total=False):
    place_id:      str
    name:          str
    source:        str            # "geoapify" | "foursquare" | "google"
    latitude:      float
    longitude:     float
    city:          Optional[str]
    state:         Optional[str]
    country:       Optional[str]
    postcode:      Optional[str]
    street:        Optional[str]
    suburb:        Optional[str]
    district:      Optional[str]
    address:       Optional[str]   # pre-formatted full address string ready to display
    categories:    list[str]      # raw category strings from the source API
    price_level:   Optional[int]  # 1–4
    rating:        Optional[float]
    review_count:  Optional[int]
    hours:         Optional[str]
    attributes:    Optional[dict[str, Any]]   # GoodForKids, DogsAllowed, etc.
    tags:          Optional[list[str]]        # filled in by Stage 1
    score:          Optional[float]
    score_breakdown: Optional[dict[str, float]]
    fallback:       bool


class UserPreference(TypedDict, total=False):
    # direct mapping of the onboarding survey — backend stores verbatim and
    # passes it straight here, so field names and values must match exactly
    user_id:              str

    # Section 1 — Context
    use_case:             str          # "local" | "daytrip" | "travel" | "mixed"
    party_type:           str          # "solo" | "couple" | "friends" | "family" | "mixed"

    # Section 2 — Budget  (1 = free/budget, 4 = luxury)
    daily_budget_tier:    int
    trip_budget_tier:     Optional[int]   # None for local users ("not applicable")

    # Section 3 — Activities & Interests
    preferred_tags:       list[str]    # subset of the 15 place tags
    exploration_score:    int          # 1–5 (1 = stick to known, 5 = always something new)
    popularity_weight:    int          # 1–5 (1 = ignore reviews, 5 = highly reviewed only)

    # Section 4 — Food & Dining
    cuisine_preferences:  list[str]    # see ALL_CUISINES in user_profiler.py
    dietary_restrictions: list[str]    # see ALL_DIETARY in user_profiler.py

    # Section 5 — Getting Around
    travel_mode:          list[str]    # ["walk"] | ["bike"] | ["transit"] | ["drive"]
    max_travel_minutes:   str          # "< 10" | "10-20" | "20-40" | "> 40"
    itinerary_pace:       str          # "packed" (6/day) | "balanced" (4) | "relaxed" (2)

    # Section 6 — Revisit behaviour
    # False (default): each place appears at most once across all days
    # True: food_and_drink places can repeat across days; landmarks/cultural blocked after first visit
    allow_revisits:       bool


class UserVisit(TypedDict, total=False):
    user_id:     str
    place_id:    str
    rating:      Optional[float]   # 1–5; None if not explicitly rated
    visit_count: int                # ≥ 1
    tags:        list[str]          # Stage 1 tags used as the CF signal
    created_at:  Optional[str]      # ISO-8601; used for recency decay at train time
