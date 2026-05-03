from typing import Optional
from pydantic import BaseModel

class placeModel(BaseModel):
    place_id: str
    name: str
    categories: list[str]
    hours: Optional[str]
    country: str
    state: str
    city: str
    street: str
    postcode: str
    latitude: float
    longitude: float

class placeInput(placeModel):
    pass