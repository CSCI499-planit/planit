from pydantic import BaseModel


class ratingsModel(BaseModel):
    rating: str
    place_id: str


class ratingsInput(ratingsModel):
    pass