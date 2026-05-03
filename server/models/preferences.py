from pydantic import BaseModel


class preferenceModel(BaseModel):
    use_case: str
    party_type: str
    daily_budget_tier: int
    trip_budget_tier: int
    preferred_tags: list[str]
    exploration_score: int
    popularity_weight: int
    cuisine_preferences: list[str]
    dietary_restrictions: list[str]
    travel_mode: list[str]
    max_travel_minutes: str
    itinerary_pace: str


class preferenceInput(preferenceModel):
    pass