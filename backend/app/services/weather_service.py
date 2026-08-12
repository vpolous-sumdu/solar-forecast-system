import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.station import Station
from app.models.weather import WeatherForecast

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_and_save_weather(db: Session, station_id: int) -> int:
    """
    Завантажує погодинний прогноз погоди на 48 годин з Open-Meteo
    та зберігає/оновлює його у хмарній базі даних Neon PostgreSQL.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )


    params = {
        "latitude": station.latitude,
        "longitude": station.longitude,
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,cloud_cover,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "forecast_days": 2
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Помилка підключення до сервісу погоди Open-Meteo: {str(e)}"
        )

    hourly_data = data.get("hourly", {})
    timestamps = hourly_data.get("time", [])
    temperatures = hourly_data.get("temperature_2m", [])
    cloud_covers = hourly_data.get("cloud_cover", [])
    pressures = hourly_data.get("surface_pressure", [])
    humidities = hourly_data.get("relative_humidity_2m", [])
    wind_speeds = hourly_data.get("wind_speed_10m", [])

    saved_count = 0

    for i in range(len(timestamps)):
        # Конвертуємо ISO рядок "2026-08-12T14:00" у datetime об'єкт з часовим поясом UTC
        dt_naive = datetime.fromisoformat(timestamps[i])
        dt_utc = dt_naive.replace(tzinfo=timezone.utc)

        # Перевіряємо чи є вже прогноз на цю годину у базі Neon
        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.timestamp == dt_utc
        ).first()

        if existing:
            existing.temperature = temperatures[i]
            existing.cloud_cover = cloud_covers[i]
            existing.pressure = pressures[i]
            existing.humidity = humidities[i]
            existing.wind_speed = wind_speeds[i]
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temperatures[i],
                cloud_cover=cloud_covers[i],
                pressure=pressures[i],
                humidity=humidities[i],
                wind_speed=wind_speeds[i]
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count
