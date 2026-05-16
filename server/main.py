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
from server.routes.recommend import router as recommend_route
from server.routes.interactions import router as interaction_route
from server.routes.imports import router as import_route
from server.routes.wake import router as wake_route

load_dotenv()

API_PORT = os.getenv('API_PORT', '8000')
API_HOST = os.getenv('API_HOST', '')
PRODUCTION_URL = os.getenv('PRODUCTION_URL', '')
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '')
app = FastAPI()

origins = {
    'http://localhost:3000',
    'http://localhost:5173',   # Vite dev server
    'http://127.0.0.1:5173',
    'null',                    # file:// POC opened directly in browser
}

if PRODUCTION_URL:
    origins.add(f'https://{PRODUCTION_URL}')

for origin in ALLOWED_ORIGINS.split(','):
    origin = origin.strip()
    if origin:
        origins.add(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(origins),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(user_route)
app.include_router(preference_route)
app.include_router(recommend_route)
app.include_router(interaction_route)
app.include_router(import_route)
app.include_router(wake_route)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "planit-backend",
        "ml_service_configured": bool(os.getenv("ML_SERVICE_URL", "")),
    }


if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=int(API_PORT))
