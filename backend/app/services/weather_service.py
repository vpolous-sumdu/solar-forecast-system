import requests
import numpy as np
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
    Завантажує прогноз погоди з OpenWeatherMap, лінійно інтерполює його з 3-годинних засічок
    у погодинний 24-годинний ряд на завтра (1-в-1 з AddMeteoData у unit2.py)
    та зберігає в базу даних Neon із позначкою source='OpenWeatherMap'.
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
    if not weather_list:
        return 0

    tz_offset_sec = int(data.get("city", {}).get("timezone", 10800))

    # 1. Збираємо 3-годинні точки від OpenWeatherMap за МІСЦЕВИМ часом (1-в-1 з open_weather_map_unit.py)
    owm_points = []
    for item in weather_list:
        dt_utc = datetime.fromtimestamp(int(item["dt"]), tz=timezone.utc)
        dt_local = dt_utc + timedelta(seconds=tz_offset_sec)
        owm_points.append({
            "local_dt": dt_local,
            "hh": dt_local.hour + dt_local.minute / 60.0,
            "temp": float(item["main"]["temp"]),
            "cloud": float(item.get("clouds", {}).get("all", 0.0)),
            "pressure": float(item["main"]["pressure"]),
            "humidity": float(item["main"]["humidity"]),
            "wind": float(item.get("wind", {}).get("speed", 0.0))
        })

    owm_points.sort(key=lambda x: x["local_dt"])

    # 2. Формуємо 24 погодинні точки строго за МІСЦЕВИМ часом на ЗАВТРА (00:00 - 23:00)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc + timedelta(seconds=tz_offset_sec)
    tomorrow_local = (now_local + timedelta(days=1)).date()
    saved_count = 0

    for hour in range(24):
        target_dt_local = datetime(tomorrow_local.year, tomorrow_local.month, tomorrow_local.day, hour, 0, 0, tzinfo=timezone.utc)

        # Точна прив'язка метеоданих 1-в-1 з Delphi AddMeteoData (функція Incl: пошук 3h засічки Am[j].hh >= hour)
        matched_point = None
        for pt in owm_points:
            if pt["local_dt"].date() == tomorrow_local and pt["hh"] >= hour:
                matched_point = pt
                break
        
        if not matched_point:
            # Запасний варіант: найближча засічка за датою/часом
            for pt in owm_points:
                if pt["local_dt"].date() == tomorrow_local:
                    matched_point = pt
            if not matched_point:
                matched_point = owm_points[-1]

        t_val = matched_point["temp"]
        c_val = matched_point["cloud"]
        p_val = matched_point["pressure"]
        h_val = matched_point["humidity"]
        w_val = matched_point["wind"]

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.timestamp == target_dt_local
        ).first()

        if existing:
            existing.temperature = round(t_val, 2)
            existing.cloud_cover = round(c_val, 1)
            existing.pressure = round(p_val, 1)
            existing.humidity = round(h_val, 1)
            existing.wind_speed = round(w_val, 2)
            existing.source = "OpenWeatherMap"
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=target_dt_local,
                temperature=round(t_val, 2),
                cloud_cover=round(c_val, 1),
                pressure=round(p_val, 1),
                humidity=round(h_val, 1),
                wind_speed=round(w_val, 2),
                source="OpenWeatherMap"
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count
