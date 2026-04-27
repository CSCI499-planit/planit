from pydantic import BaseModel
from datetime import datetime

class userModel(BaseModel):
    username: str
    email:str
    password:str

class userInput(userModel):
    pass

class userOutput(userModel):
    id:str
    created_at: datetime