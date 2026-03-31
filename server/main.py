"""
    back-end API entry
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

load_dotenv()

API_PORT = os.getenv('API_PORT','8000')
API_HOST = os.getenv('API_HOST','')
app = FastAPI()

origins = [
    'http://localhost'
    'https://[Real_URL_GOES_HERE]'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

#app.include_router()

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST,port=int(API_PORT))
