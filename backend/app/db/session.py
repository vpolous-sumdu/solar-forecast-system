import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Отримуємо Connection Strings з .env (Pooled для API, Direct для міграцій)

DATABASE_URL = os.getenv("DATABASE_URL")
DIRECT_DATABASE_URL = os.getenv("DIRECT_DATABASE_URL")

# Engine для постійної роботи API
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# SessionFactory для створення підключень до СУБД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовий клас для всіх моделей БД
Base = declarative_base()

def get_db():
    """Dependency для передачі сесії БД у FastAPI ендпоінти"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
