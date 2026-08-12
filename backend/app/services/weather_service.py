import requests
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.station import Station
from app.models.weather import WeatherForecast

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OWM_APPID = "4d42571040d0367f79e4a83bfb696d4a"
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"

def fetch_and_save_weather(db: Session, station_id: int) -> int:
    """
    Завантажує погодинний прогноз погоди на завтра з Open-Meteo
    та зберігає/оновлює його у хмарній базі даних Neon PostgreSQL.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    params = {
        "latitude": station.latitude,
        "longitude": station.longitude,
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,cloud_cover,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "start_date": tomorrow.isoformat(),
        "end_date": tomorrow.isoformat()
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
        dt_utc = datetime.fromisoformat(timestamps[i]).replace(tzinfo=timezone.utc)

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
            existing.source = "Open-Meteo"
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temperatures[i],
                cloud_cover=cloud_covers[i],
                pressure=pressures[i],
                humidity=humidities[i],
                wind_speed=wind_speeds[i],
                source="Open-Meteo"
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count

def fetch_and_save_owm_weather(db: Session, station_id: int) -> int:
    """
    Завантажує прогноз погоди з OpenWeatherMap (еталонний API ключ)
    та зберігає його в базу даних із позначкою source='OpenWeatherMap'.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    params = {
        "lat": station.latitude,
        "lon": station.longitude,
        "units": "metric",
        "appid": OWM_APPID
    }

    try:
        response = requests.get(OWM_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Помилка підключення до OpenWeatherMap: {str(e)}"
        )

    weather_list = data.get("list", [])
    saved_count = 0

    for item in weather_list:
        dt_timestamp = int(item["dt"])
        dt_utc = datetime.fromtimestamp(dt_timestamp, tz=timezone.utc)

        temp = float(item["main"]["temp"])
        pressure = float(item["main"]["pressure"])
        humidity = float(item["main"]["humidity"])
        cloud_cover = float(item.get("clouds", {}).get("all", 0.0))
        wind_speed = float(item.get("wind", {}).get("speed", 0.0))

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.timestamp == dt_utc
        ).first()

        if existing:
            existing.temperature = temp
            existing.cloud_cover = cloud_cover
            existing.pressure = pressure
            existing.humidity = humidity
            existing.wind_speed = wind_speed
            existing.source = "OpenWeatherMap"
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temp,
                cloud_cover=cloud_cover,
                pressure=pressure,
                humidity=humidity,
                wind_speed=wind_speed,
                source="OpenWeatherMap"
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count
