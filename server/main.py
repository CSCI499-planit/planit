"""
    back-end API entry
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from server.routes.users import router as user_route
from server.routes.preferences import router as preference_route
from server.routes.likes import router as rating_route
from server.routes.places import router as place_route

load_dotenv()

API_PORT = os.getenv('API_PORT','8000')
API_HOST = os.getenv('API_HOST','')
PRODUCTION_URL = os.getenv('PRODUCTION_URL','')
app = FastAPI()

origins = [
    'http://localhost:3000',
    f'https://{PRODUCTION_URL}'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(user_route)
app.include_router(preference_route)
app.include_router(rating_route)
app.include_router(place_route)

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=int(API_PORT))
