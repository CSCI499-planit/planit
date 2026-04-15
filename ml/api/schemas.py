from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel


class UserPreferenceSchema(BaseModel):
    user_id: str

    use_case:   str = "travel"    # "local" | "daytrip" | "travel" | "mixed"
    party_type: str = "solo"      # "solo" | "couple" | "friends" | "family" | "mixed"

    daily_budget_tier: int = 2
    trip_budget_tier:  Optional[int] = None

    preferred_tags:    list[str] = []
    exploration_score: int = 3    # 1–5
    popularity_weight: int = 3    # 1–5

    cuisine_preferences:  list[str] = []
    dietary_restrictions: list[str] = []

    travel_mode:        list[str] = ["transit"]
    max_travel_minutes: str = "20-40"
    itinerary_pace:     str = "balanced"    # "packed" | "balanced" | "relaxed"


class UserVisitSchema(BaseModel):
    user_id:     str
    place_id:    str
    rating:      Optional[float] = None
    visit_count: int = 1
    tags:        list[str] = []


class PlaceRecordSchema(BaseModel):
    place_id:     str
    name:         str = ""
    source:       str = ""
    latitude:     float = 0.0
    longitude:    float = 0.0
    city:         Optional[str] = None
    state:        Optional[str] = None
    country:      Optional[str] = None
    postcode:     Optional[str] = None
    street:       Optional[str] = None
    suburb:       Optional[str] = None
    district:     Optional[str] = None
    categories:   list[str] = []
    price_level:  Optional[int] = None
    rating:       Optional[float] = None
    review_count: Optional[int] = None
    hours:        Optional[str] = None
    attributes:   Optional[dict[str, Any]] = None
    tags:         Optional[list[str]] = None

    score:          Optional[float] = None
    _cf_score:      Optional[float] = None
    _tag_score:     Optional[float] = None
    _pop_score:     Optional[float] = None
    _cuisine_bonus: Optional[float] = None
    _party_match:   Optional[float] = None
    _fallback:      Optional[bool]  = None


class RecommendRequest(BaseModel):
    preference: UserPreferenceSchema
    places:     list[PlaceRecordSchema]
    visits:     Optional[list[UserVisitSchema]] = None
    top_k:      int = 20


class RecommendResponse(BaseModel):
    places: list[PlaceRecordSchema]


class ItineraryRequest(BaseModel):
    preference:  UserPreferenceSchema
    places:      list[PlaceRecordSchema]
    visits:      Optional[list[UserVisitSchema]] = None
    top_k:       int = 20
    trip_days:   int = 1
    start_date:  Optional[str] = None


class TravelLegSchema(BaseModel):
    mode:       str
    minutes:    int
    distance_m: int


class StopSchema(BaseModel):
    place:          PlaceRecordSchema
    arrival_time:   str
    departure_time: str
    travel_to_next: Optional[TravelLegSchema] = None


class DaySchema(BaseModel):
    day:   int
    date:  Optional[str] = None
    stops: list[StopSchema]


class ItineraryResponse(BaseModel):
    itinerary: list[DaySchema]


class EmbedRequest(BaseModel):
    preference: UserPreferenceSchema
    visits:     Optional[list[UserVisitSchema]] = None


class EmbedResponse(BaseModel):
    user_id:   str
    embedding: list[float]


class SimilarUsersRequest(BaseModel):
    embedding: list[float]
    top_k:     int = 10


class SimilarUsersResponse(BaseModel):
    users: list[dict]
