from pydantic import BaseModel
from datetime import datetime

class ratingsModel(BaseModel):
    rating: str
    place_id: str

class ratingsInput(ratingsModel):
    pass

class ratingsOutput(ratingsModel):
    user_id: str
    created_at: datetime