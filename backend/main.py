from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import engine, Base
from app.api.stations import router as stations_router

# Автоматично створюємо таблиці у PostgreSQL при старті (якщо їх ще немає)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Solar Forecast System API",
    description="REST API сервіс прогнозування генерації сонячних електростанцій (СЕС)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Дотримуємося fastapi skill: Налаштування CORS для майбутнього Angular фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Дозволяємо запити з будь-якого фронтенду
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Підключаємо роутер станцій під префіксом /api/v1
app.include_router(stations_router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "status": "online",
        "system": "Solar Forecast System API",
        "docs": "/docs"
    }
