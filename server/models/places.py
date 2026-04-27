from pydantic import BaseModel

class placeModel(BaseModel):
    id:str
    name:str
    categories: list[str]
    hours: dict[str,str]
    country:str
    state:str
    city:str
    street:str
    postcode:str
    lat:float
    lon:float

class placeInput(placeModel):
    pass