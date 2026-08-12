import sys
import os
from contextlib import asynccontextmanager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

from app.api.stations import router as stations_router
from app.api.weather import router as weather_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматичний накат міграцій Alembic при старті FastAPI на Render
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        
        direct_db_url = os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL")
        if direct_db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", direct_db_url)
            
        print("Running automatic Alembic migrations on startup...")
        command.upgrade(alembic_cfg, "head")
        print("Alembic migrations successfully applied!")
    except Exception as e:
        print(f"Warning: Automatic migration failed: {str(e)}")
        
    yield

app = FastAPI(
    title="Solar Forecast System API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stations_router, prefix="/api/v1")
app.include_router(weather_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"status": "online", "docs": "/docs"}
