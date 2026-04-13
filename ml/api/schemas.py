"""
    Pydantic request/response models for the ML API.
    These mirror the TypedDicts in ml/data/preprocess.py — Pydantic gives us
    automatic validation and clear error messages when the server sends bad data.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel


# --- Input: user survey ---

class UserPreferenceSchema(BaseModel):
    user_id: str

    # what kind of trip
    use_case: str = "travel"           # "local" | "daytrip" | "travel" | "mixed"
    party_type: str = "solo"           # "solo" | "couple" | "friends" | "family" | "mixed"

    # budget (1=free/budget → 4=luxury)
    daily_budget_tier: int = 2
    trip_budget_tier: Optional[int] = None

    # activity preferences
    preferred_tags: list[str] = []
    exploration_score: int = 3         # 1–5
    popularity_weight: int = 3         # 1–5

    # food
    cuisine_preferences: list[str] = []
    dietary_restrictions: list[str] = []

    # getting around
    travel_mode: list[str] = ["transit"]
    max_travel_minutes: str = "20-40"
    itinerary_pace: str = "balanced"   # "packed" | "balanced" | "relaxed"


# --- Input: a single user–place interaction ---

class UserVisitSchema(BaseModel):
    user_id: str
    place_id: str
    rating: Optional[float] = None     # 1–5; None if not explicitly rated
    visit_count: int = 1
    tags: list[str] = []


# --- Input/Output: a place ---

class PlaceRecordSchema(BaseModel):
    place_id: str
    name: str = ""
    source: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postcode: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    district: Optional[str] = None
    categories: list[str] = []
    price_level: Optional[int] = None  # 1–4
    rating: Optional[float] = None
    review_count: Optional[int] = None
    hours: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None

    # added by stage 3 — not present in input
    score: Optional[float] = None

    # score breakdown — only present in /recommend and /itinerary responses
    _cf_score:      Optional[float] = None
    _tag_score:     Optional[float] = None
    _pop_score:     Optional[float] = None
    _cuisine_bonus: Optional[float] = None
    _party_match:   Optional[float] = None
    _fallback:      Optional[bool]  = None


# --- Request/Response bodies ---

class RecommendRequest(BaseModel):
    preference: UserPreferenceSchema
    places: list[PlaceRecordSchema]
    visits: Optional[list[UserVisitSchema]] = None   # Google Takeout history if available
    top_k: int = 20


class RecommendResponse(BaseModel):
    places: list[PlaceRecordSchema]   # ranked, each has a "score" field


class ItineraryRequest(BaseModel):
    preference: UserPreferenceSchema
    places: list[PlaceRecordSchema]
    visits: Optional[list[UserVisitSchema]] = None
    top_k: int = 20
    trip_days: int = 1
    start_date: Optional[str] = None   # "YYYY-MM-DD"


class TravelLegSchema(BaseModel):
    mode: str
    minutes: int
    distance_m: int


class StopSchema(BaseModel):
    place: PlaceRecordSchema
    arrival_time: str
    departure_time: str
    travel_to_next: Optional[TravelLegSchema] = None


class DaySchema(BaseModel):
    day: int
    date: Optional[str] = None
    stops: list[StopSchema]


class ItineraryResponse(BaseModel):
    itinerary: list[DaySchema]


class EmbedRequest(BaseModel):
    preference: UserPreferenceSchema
    visits: Optional[list[UserVisitSchema]] = None


class EmbedResponse(BaseModel):
    user_id: str
    embedding: list[float]            # 48-dim vector


class SimilarUsersRequest(BaseModel):
    embedding: list[float]            # 48-dim vector from /profile/embed
    top_k: int = 10


class SimilarUsersResponse(BaseModel):
    users: list[dict]                 # [{"user_id": str, "similarity": float}]
