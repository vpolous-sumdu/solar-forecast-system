import numpy as np
from datetime import datetime, date, timezone
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
        target_date: Optional[date] = None,
        weather_source: str = "OpenWeatherMap",
        model_id: Optional[int] = None
) -> List[dict]:
    """
    Розраховує прогноз генерації за ВКАЗАНИМ ДЖЕРЕЛОМ ПОГОДИ, ДАТОЮ та ВКАЗАНОЮ МОДЕЛЛЮ.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    # Фільтруємо погоду під обране джерело (OpenWeatherMap / Open-Meteo) та обрану дату
    weather_query = db.query(WeatherForecast).filter(
        WeatherForecast.station_id == station_id,
        WeatherForecast.source == weather_source
    )

    if target_date is not None:
        start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        weather_query = weather_query.filter(
            WeatherForecast.timestamp >= start_dt,
            WeatherForecast.timestamp <= end_dt
        )

    weather_records = weather_query.order_by(WeatherForecast.timestamp.asc()).all()

    if not weather_records:
        date_info = f" на дату {target_date.isoformat()}" if target_date else ""
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Немає збереженої погоди від джерела {weather_source} для станції #{station_id}{date_info}. Спочатку завантажте погоду."
        )

    # Завантажуємо модель з БД
    if model_id:
        model_record = db.query(NeuralModel).filter(
            NeuralModel.id == model_id,
            NeuralModel.station_id == station_id
        ).first()
    else:
        model_record = db.query(NeuralModel).filter(
            NeuralModel.station_id == station_id
        ).order_by(NeuralModel.id.asc()).first()


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

    weather_timestamps = [w.timestamp for w in weather_records]
    existing_gen_map = {
        g.timestamp: g for g in db.query(GenerationForecast).filter(
            GenerationForecast.station_id == station_id,
            GenerationForecast.weather_source == weather_source,
            GenerationForecast.model_id == model_record.id,
            GenerationForecast.timestamp.in_(weather_timestamps)
        ).all()
    }

    results = []
    for i, w in enumerate(weather_records):
        val = raw_predictions[i]
        if val < 0: val = 0.0
        if w.elevation < -0.4: val = 0.0

        predicted_watts = round(float(val), 6)
        predicted_kw = round(float(val / 1000.0), 4)

        # Зберігаємо прогноз із чіткою прив'язкою до weather_source та model_id
        existing_gen = existing_gen_map.get(w.timestamp)

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
        target_date: Optional[date] = None,
        weather_source: Optional[str] = None,
        model_id: Optional[int] = None
) -> List[dict]:
    """Отримує збережений прогноз генерації з фільтром по даті, джерелу прогнозу погоди та моделі"""
    query = db.query(GenerationForecast, WeatherForecast).join(
        WeatherForecast,
        (GenerationForecast.station_id == WeatherForecast.station_id) &
        (GenerationForecast.timestamp == WeatherForecast.timestamp) &
        (GenerationForecast.weather_source == WeatherForecast.source)
    ).filter(
        GenerationForecast.station_id == station_id
    )

    if target_date is not None:
        start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        query = query.filter(
            GenerationForecast.timestamp >= start_dt,
            GenerationForecast.timestamp <= end_dt
        )

    if weather_source and weather_source.upper() != "ALL":
        query = query.filter(GenerationForecast.weather_source == weather_source)

    if model_id:
        query = query.filter(GenerationForecast.model_id == model_id)

    saved_records = query.order_by(GenerationForecast.timestamp.asc(), GenerationForecast.weather_source.asc()).all()

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



def run_batch_forecast_for_all_stations(
        db: Session,
        target_date: Optional[date] = None,
        weather_source: str = "ALL",
        model_id: Optional[int] = None
) -> dict:
    """
    Пакетно завантажує прогноз погоди та генерує прогноз генерації для ВСІХ зареєстрованих станцій.
    Підтримує одночасний розрахунок для кількох джерел погоди (weather_source="ALL" або "OpenWeatherMap,Open-Meteo").
    Ідеально підходить для Cron-планувальника або фонового виконання о 23:05.
    """
    from datetime import timedelta
    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    from app.services.weather_service import (
        fetch_and_save_weather,
        fetch_and_save_owm_weather,
        fetch_and_save_archive_weather,
        fetch_and_save_visual_crossing_weather
    )

    stations = db.query(Station).order_by(Station.id.asc()).all()
    if not stations:
        return {
            "status": "warning",
            "message": "Немає зареєстрованих станцій у базі даних.",
            "target_date": target_date.isoformat(),
            "weather_source": weather_source,
            "stations_total": 0,
            "stations_processed": 0,
            "total_predicted_kwh": 0.0,
            "details": []
        }

    # Визначаємо список джерел погоди для обробки
    if weather_source.upper() == "ALL":
        sources_to_process = ["OpenWeatherMap", "Open-Meteo", "Visual-Crossing"]
    elif "," in weather_source:
        sources_to_process = [s.strip() for s in weather_source.split(",") if s.strip()]
    else:
        sources_to_process = [weather_source]

    processed_count = 0
    total_predicted_kwh = 0.0
    details = []

    for src in sources_to_process:
        src_processed = 0
        src_kwh = 0.0
        src_details = []

        for s in stations:
            try:
                # 1. Завантажуємо погоду для конкретного джерела
                if src == "Open-Meteo":
                    fetch_and_save_weather(db, s.id, target_date=target_date)
                elif src == "Open-Meteo-Archive":
                    fetch_and_save_archive_weather(db, s.id, target_date=target_date)
                elif src == "Visual-Crossing":
                    fetch_and_save_visual_crossing_weather(db, s.id, target_date=target_date)
                else:
                    fetch_and_save_owm_weather(db, s.id, target_date=target_date)


                # 2. Визначаємо моделі: якщо model_id не задано — автоматично рахуємо для ВСІХ зареєстрованих моделей СЕС
                if model_id:
                    target_models = db.query(NeuralModel).filter(
                        NeuralModel.id == model_id,
                        NeuralModel.station_id == s.id
                    ).all()
                else:
                    target_models = db.query(NeuralModel).filter(
                        NeuralModel.station_id == s.id
                    ).order_by(NeuralModel.id.asc()).all()

                if not target_models:
                    continue

                for m in target_models:
                    gen_results = generate_power_forecast_for_station(
                        db=db,
                        station_id=s.id,
                        target_date=target_date,
                        weather_source=src,
                        model_id=m.id
                    )

                    station_daily_kwh = sum(item["predicted_power_kw"] for item in gen_results)
                    src_kwh += station_daily_kwh
                    src_processed += 1

                    src_details.append({
                        "station_id": s.id,
                        "station_name": s.name,
                        "model_id": m.id,
                        "model_name": m.name,
                        "status": "success",
                        "predicted_daily_kwh": round(station_daily_kwh, 2),
                        "hourly_points": len(gen_results)
                    })
            except Exception as e:
                db.rollback()
                src_details.append({
                    "station_id": s.id,
                    "station_name": s.name,
                    "status": "error",
                    "error": str(e)
                })

        processed_count += src_processed
        total_predicted_kwh += src_kwh
        details.append({
            "weather_source": src,
            "stations_processed": src_processed,
            "subtotal_predicted_kwh": round(src_kwh, 2),
            "stations": src_details
        })

    return {
        "status": "success",
        "target_date": target_date.isoformat(),
        "weather_sources": sources_to_process,
        "stations_total": len(stations),
        "total_operations_processed": processed_count,
        "total_predicted_kwh": round(total_predicted_kwh, 2),
        "details": details
    }


