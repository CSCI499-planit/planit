from pydantic import BaseModel


class userModel(BaseModel):
    username: str
    email: str
    password: str


class userInput(userModel):
    pass