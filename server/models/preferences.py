from pydantic import BaseModel
from datetime import datetime

class preferenceModel(BaseModel):
    use_case: str
    part_type: str
    daily_budget_tier:str
    trip_budget_tier: str
    preferred_tags: list[str]
    exploration_score:str
    popularity_weight: str
    cuisines_preferences: list[str]
    dietary_restrictions: list[str]
    travel_mode: list[str]
    max_travel_minutes: str
    itinerary_pace: str

class preferenceInput(preferenceModel):
    pass

class preferenceOutput(preferenceModel):
    id:str
    user_id:str
    created_at:datetime