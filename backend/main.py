import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.stations import router as stations_router

app = FastAPI(title="Solar Forecast System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stations_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "online", "docs": "/docs"}
