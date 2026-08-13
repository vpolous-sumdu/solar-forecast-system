import numpy as np
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.station import Station
from app.models.weather import WeatherForecast
from app.models.neural_model import NeuralModel
from app.models.generation import GenerationForecast

from app.services.models.model_registry import execute_model_prediction


def generate_power_forecast_for_station(
    db: Session,
    station_id: int,
    weather_source: str = "OpenWeatherMap",
    model_id: Optional[int] = None
) -> List[dict]:
    """
    Розраховує прогноз генерації за ВКАЗАНИМ ДЖЕРЕЛОМ ПОГОДИ та ВКАЗАНОЮ МОДЕЛЛЮ.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    # Фільтруємо погоду СТРОГО під обране джерело (OpenWeatherMap / Open-Meteo)
    weather_records = db.query(WeatherForecast).filter(
        WeatherForecast.station_id == station_id,
        WeatherForecast.source == weather_source
    ).order_by(WeatherForecast.timestamp.asc()).all()

    if not weather_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Немає збереженої погоди від джерела {weather_source} для станції #{station_id}. Спочатку завантажте погоду."
        )

    # Завантажуємо модель з БД
    if model_id:
        model_record = db.query(NeuralModel).filter(
            NeuralModel.id == model_id,
            NeuralModel.station_id == station_id
        ).first()
    else:
        model_record = db.query(NeuralModel).filter(
            NeuralModel.station_id == station_id,
            NeuralModel.is_active == True
        ).first()

    if not model_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ваги нейромережі для станції #{station_id} не знайдено в БД."
        )

    weights_dict = model_record.weights

    mas_in = np.array([
        [float(w.st_s) for w in weather_records],
        [float(w.temperature) for w in weather_records],
        [float(w.h_svetl) for w in weather_records],
        [float(w.cloud_cover) for w in weather_records],
        [float(w.azimuth) for w in weather_records],
        [float(w.elevation) for w in weather_records],
        [float(w.ww) for w in weather_records]
    ], dtype=np.float64)

    # Викликаємо модель ДИНАМІЧНО за її кодом з бази даних (baseline, v2_experimental тощо)
    model_code = getattr(model_record, "code", "baseline") or "baseline"
    raw_predictions = execute_model_prediction(model_code, mas_in, weights_dict)



    results = []
    for i, w in enumerate(weather_records):
        val = raw_predictions[i]
        if val < 0: val = 0.0
        if w.elevation < -0.4: val = 0.0

        predicted_watts = round(float(val), 6)
        predicted_kw = round(float(val / 1000.0), 4)

        # Зберігаємо прогноз із чіткою прив'язкою до weather_source та model_id
        existing_gen = db.query(GenerationForecast).filter(
            GenerationForecast.station_id == station_id,
            GenerationForecast.weather_source == weather_source,
            GenerationForecast.model_id == model_record.id,
            GenerationForecast.timestamp == w.timestamp
        ).first()

        if existing_gen:
            existing_gen.predicted_power_watts = predicted_watts
            existing_gen.predicted_power_kw = predicted_kw
        else:
            gen_record = GenerationForecast(
                station_id=station_id,
                model_id=model_record.id,
                weather_source=weather_source,
                timestamp=w.timestamp,
                predicted_power_watts=predicted_watts,
                predicted_power_kw=predicted_kw
            )
            db.add(gen_record)

        results.append({
            "timestamp": w.timestamp,
            "st_s": w.st_s,
            "elevation": w.elevation,
            "azimuth": w.azimuth,
            "predicted_power_watts": predicted_watts,
            "predicted_power_kw": predicted_kw,
            "source": weather_source,
            "model_id": model_record.id
        })

    db.commit()
    return results

def get_saved_forecast_for_station(
    db: Session,
    station_id: int,
    weather_source: Optional[str] = None
) -> List[dict]:
    """Отримує збережений прогноз генерації з фільтром по weather_source"""
    query = db.query(GenerationForecast, WeatherForecast).join(
        WeatherForecast,
        (GenerationForecast.station_id == WeatherForecast.station_id) & 
        (GenerationForecast.timestamp == WeatherForecast.timestamp) &
        (GenerationForecast.weather_source == WeatherForecast.source)
    ).filter(
        GenerationForecast.station_id == station_id
    )

    if weather_source:
        query = query.filter(GenerationForecast.weather_source == weather_source)

    saved_records = query.order_by(GenerationForecast.timestamp.asc()).all()

    results = []
    for gen, w in saved_records:
        results.append({
            "timestamp": gen.timestamp,
            "st_s": w.st_s,
            "elevation": w.elevation,
            "azimuth": w.azimuth,
            "predicted_power_watts": gen.predicted_power_watts,
            "predicted_power_kw": gen.predicted_power_kw,
            "source": gen.weather_source,
            "model_id": gen.model_id
        })
    return results
