from pydantic import BaseModel


class ratingsModel(BaseModel):
    rating: float
    place_id: str


class ratingsInput(ratingsModel):
    pass