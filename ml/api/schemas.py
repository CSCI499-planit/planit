from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class UserPreferenceSchema(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)

    use_case:   str = "travel"    # "local" | "daytrip" | "travel" | "mixed"
    party_type: str = "solo"      # "solo" | "couple" | "friends" | "family" | "mixed"

    daily_budget_tier: int = Field(2, ge=1, le=5)
    trip_budget_tier:  Optional[int] = Field(None, ge=1, le=5)

    preferred_tags:    list[str] = Field(default_factory=list, max_length=25)
    exploration_score: int = Field(3, ge=1, le=5)
    popularity_weight: int = Field(3, ge=1, le=5)

    cuisine_preferences:  list[str] = Field(default_factory=list, max_length=25)
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=25)

    travel_mode:        list[str] = Field(default_factory=lambda: ["transit"], max_length=5)
    max_travel_minutes: str = "20-40"
    itinerary_pace:     str = "balanced"    # "packed" | "balanced" | "relaxed"
    allow_revisits:     bool = False


class UserVisitSchema(BaseModel):
    user_id:     str = Field(..., min_length=1, max_length=128)
    place_id:    str = Field(..., min_length=1, max_length=256)
    rating:      Optional[float] = Field(None, ge=0, le=5)
    visit_count: int = Field(1, ge=1, le=10_000)
    tags:        list[str] = Field(default_factory=list, max_length=25)
    created_at:  Optional[str] = None


class PlaceRecordSchema(BaseModel):
    place_id:     str = Field(..., min_length=1, max_length=256)
    name:         str = ""
    source:       str = ""
    latitude:     float = Field(0.0, ge=-90, le=90)
    longitude:    float = Field(0.0, ge=-180, le=180)
    city:         Optional[str] = None
    state:        Optional[str] = None
    country:      Optional[str] = None
    postcode:     Optional[str] = None
    street:       Optional[str] = None
    suburb:       Optional[str] = None
    district:     Optional[str] = None
    address:      Optional[str] = None   # pre-formatted full address, ready to display
    categories:   list[str] = Field(default_factory=list, max_length=50)
    price_level:  Optional[int] = Field(None, ge=0, le=5)
    rating:       Optional[float] = Field(None, ge=0, le=5)
    review_count: Optional[int] = Field(None, ge=0)
    hours:        Optional[str] = None
    attributes:   Optional[dict[str, Any]] = None
    tags:         Optional[list[str]] = Field(None, max_length=25)

    score:           Optional[float] = Field(None, ge=0)
    score_breakdown: Optional[dict[str, float]] = None
    fallback:        bool = False


class RecommendRequest(BaseModel):
    preference:          UserPreferenceSchema
    places:              list[PlaceRecordSchema] = Field(..., min_length=1, max_length=100)
    visits:              Optional[list[UserVisitSchema]] = Field(None, max_length=1000)
    top_k:               int = Field(20, ge=1, le=50)
    excluded_place_ids:  list[str] = Field(default_factory=list, max_length=500)


class RecommendResponse(BaseModel):
    places: list[PlaceRecordSchema]


class HotelLocationSchema(BaseModel):
    latitude:  float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ItineraryRequest(BaseModel):
    preference:          UserPreferenceSchema
    places:              list[PlaceRecordSchema] = Field(..., min_length=1, max_length=100)
    visits:              Optional[list[UserVisitSchema]] = Field(None, max_length=1000)
    top_k:               int = Field(20, ge=1, le=50)
    trip_days:           int = Field(1, ge=1, le=14)
    start_date:          Optional[str] = None
    hotel_location:      Optional[HotelLocationSchema] = None
    excluded_place_ids:  list[str] = Field(default_factory=list, max_length=500)


class TravelLegSchema(BaseModel):
    mode:             str
    duration_minutes: int
    distance_m:       int


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
    visits:     Optional[list[UserVisitSchema]] = Field(None, max_length=1000)


class EmbedResponse(BaseModel):
    user_id:   str
    embedding: list[float]


class SimilarUsersRequest(BaseModel):
    embedding: list[float] = Field(..., min_length=1, max_length=1024)
    top_k:     int = Field(10, ge=1, le=50)


class SimilarUsersResponse(BaseModel):
    users: list[dict]
