import os
from datetime import datetime, date, timezone, timedelta
from typing import Optional

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.weather import WeatherForecast
from app.services.sun_service import calculate_sun_position

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OWM_APPID = os.getenv("OPENWEATHERMAP_API_KEY", "")
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"
VISUAL_CROSSING_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
VISUAL_CROSSING_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY", "")





def fetch_and_save_weather(db: Session, station_id: int, target_date: Optional[date] = None) -> int:
    """
    Завантажує погодинний прогноз погоди на обрану дату (або завтра за замовчуванням) з Open-Meteo
    та зберігає/оновлює його у хмарній базі даних Neon PostgreSQL разом із сонячними полями.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    params = {
        "latitude": station.latitude,
        "longitude": station.longitude,
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,cloud_cover,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat()
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

        # Розраховуємо сонячні та астрономічні поля 1-в-1 з unit2.py
        sun_data = calculate_sun_position(station.latitude, station.longitude, dt_utc)
        azimuth = sun_data["azimuth"]
        elevation = sun_data["elevation"]
        st_s = sun_data["st_s"]
        h_svetl = sun_data["h_svetl"]
        day_of_week = dt_utc.isoweekday()
        ww = 0.0

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.source == "Open-Meteo",
            WeatherForecast.timestamp == dt_utc
        ).first()

        if existing:
            existing.temperature = temperatures[i]
            existing.cloud_cover = cloud_covers[i]
            existing.pressure = pressures[i]
            existing.humidity = humidities[i]
            existing.wind_speed = wind_speeds[i]
            existing.source = "Open-Meteo"
            existing.st_s = st_s
            existing.h_svetl = round(h_svetl, 6)
            existing.azimuth = round(azimuth, 6)
            existing.elevation = round(elevation, 6)
            existing.day_of_week = day_of_week
            existing.ww = ww
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temperatures[i],
                cloud_cover=cloud_covers[i],
                pressure=pressures[i],
                humidity=humidities[i],
                wind_speed=wind_speeds[i],
                source="Open-Meteo",
                st_s=st_s,
                h_svetl=round(h_svetl, 6),
                azimuth=round(azimuth, 6),
                elevation=round(elevation, 6),
                day_of_week=day_of_week,
                ww=ww
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count


def _incl(mr: dict, lr_yy: int, lr_mm: int, lr_day: int, lr_hh_in: float) -> bool:
    """Точний аналог функції Incl(mr, lr) з unit2.py"""
    return (mr["yy"] == lr_yy) and (mr["mm"] == lr_mm) and (mr["day"] == lr_day) and (mr["hh"] >= lr_hh_in)


def _incl2(mr: dict, lr_yy: int, lr_mm: int, lr_day: int) -> bool:
    """Точний аналог функції Incl2(mr, lr) з unit2.py"""
    return (mr["yy"] == lr_yy) and (mr["mm"] == lr_mm) and (mr["day"] == lr_day) and (mr["hh"] >= 0)


def fetch_and_save_owm_weather(db: Session, station_id: int, target_date: Optional[date] = None) -> int:
    """
    Завантажує прогноз погоди з OpenWeatherMap та застосовує точний алгоритм
    AddMeteoData 1-в-1 з розповсюдженням даних із unit2.py + додає всі астрономічні поля!
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    if not OWM_APPID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API ключ для OpenWeatherMap не налаштовано. Будь ласка, вкажіть OPENWEATHERMAP_API_KEY у .env або Environment Variables сервера."
        )

    # Хардкоджені координати міста Суми (50.883333, 34.783333) 1-в-1 з еталоном (open_weather_map_unit.py)
    baseline_lat = 50.883333
    baseline_lon = 34.783333


    params = {
        "lat": baseline_lat,
        "lon": baseline_lon,
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

    timezone_offset = int(data.get("city", {}).get("timezone", 7200))

    # Крок 1: Заповнення масиву Am (1-в-1 з open_weather_map_unit.py)
    Am = []
    for item in weather_list[:40]:
        dt_timestamp = int(item["dt"])
        local_time = datetime.fromtimestamp(dt_timestamp + timezone_offset, tz=timezone.utc)

        Am.append({
            "yy": local_time.year,
            "mm": local_time.month,
            "day": local_time.day,
            "hh": local_time.hour + local_time.minute / 60.0 + local_time.second / 3600.0,
            "t": float(item["main"]["temp"]),
            "p0": 0.0,
            "p": float(item["main"]["pressure"]),
            "Pa": 0.0,
            "U": float(item["main"]["humidity"]),
            "DD": float(item["wind"]["deg"]),
            "Ff": float(item["wind"]["speed"]),
            "Nh": float(item.get("clouds", {}).get("all", 0.0)),
            "RRR_a": 0.0,
            "WW": 0.0 if int(item["weather"][0]["id"]) == 800 else 1.0
        })

    # Крок 2: Формування 24-годинного масиву lm на обрану дату (1-в-1 з AddMeteoData у unit2.py)
    saved_count = 0

    for hour in range(24):
        target_dt = datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0, tzinfo=timezone.utc)
        hh_in = float(hour)
        hh = float(hour + 1)

        matched_meteo = None
        interval = hh - hh_in

        if abs(3.0 - interval) <= 3.5:
            for j in range(len(Am)):
                if _incl(Am[j], target_date.year, target_date.month, target_date.day, hh_in):
                    matched_meteo = Am[j]
                    break

            if not matched_meteo:
                dt_next = datetime(target_date.year, target_date.month, target_date.day) + timedelta(days=1)
                for j in range(len(Am)):
                    if _incl2(Am[j], dt_next.year, dt_next.month, dt_next.day):
                        matched_meteo = Am[j]
                        break

        if not matched_meteo:
            for j in range(len(Am)):
                if Am[j]["yy"] == target_date.year and Am[j]["mm"] == target_date.month and Am[j][
                    "day"] == target_date.day:
                    matched_meteo = Am[j]
                    break
        if not matched_meteo and Am:
            matched_meteo = Am[0]

        temp = matched_meteo["t"]
        cloud = matched_meteo["Nh"]
        pressure = matched_meteo["p"]
        humidity = matched_meteo["U"]
        wind = matched_meteo["Ff"]
        ww = matched_meteo["WW"]

        # Розраховуємо сонячні та астрономічні поля 1-в-1 з unit2.py
        sun_data = calculate_sun_position(baseline_lat, baseline_lon, target_dt)
        azimuth = sun_data["azimuth"]
        elevation = sun_data["elevation"]
        st_s = sun_data["st_s"]
        h_svetl = sun_data["h_svetl"]
        day_of_week = target_dt.isoweekday()

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.source == "OpenWeatherMap",
            WeatherForecast.timestamp == target_dt
        ).first()

        if existing:
            existing.temperature = temp
            existing.cloud_cover = cloud
            existing.pressure = pressure
            existing.humidity = humidity
            existing.wind_speed = wind
            existing.source = "OpenWeatherMap"
            existing.st_s = st_s
            existing.h_svetl = h_svetl
            existing.azimuth = azimuth
            existing.elevation = elevation
            existing.day_of_week = day_of_week
            existing.ww = ww
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=target_dt,
                temperature=temp,
                cloud_cover=cloud,
                pressure=pressure,
                humidity=humidity,
                wind_speed=wind,
                source="OpenWeatherMap",
                st_s=st_s,
                h_svetl=h_svetl,
                azimuth=azimuth,
                elevation=elevation,
                day_of_week=day_of_week,
                ww=ww
            )

            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count


def fetch_and_save_archive_weather(db: Session, station_id: int, target_date: Optional[date] = None) -> int:
    """
    Завантажує погодинні фактичні (архівні/reanalysis) метеодані на обрану дату з Open-Meteo
    та зберігає/оновлює їх у Neon PostgreSQL з міткою джерела 'Open-Meteo-Archive'.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    if target_date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    params = {
        "latitude": station.latitude,
        "longitude": station.longitude,
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,cloud_cover,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat()
    }

    data = None
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
    except Exception:
        pass

    if not data or "hourly" not in data or not data["hourly"].get("time"):
        archive_url = "https://archive-api.open-meteo.com/v1/archive"
        try:
            response = requests.get(archive_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Помилка отримання фактичної погоди з Open-Meteo Archive: {str(e)}"
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
        sun_data = calculate_sun_position(station.latitude, station.longitude, dt_utc)
        azimuth = sun_data["azimuth"]
        elevation = sun_data["elevation"]
        st_s = sun_data["st_s"]
        h_svetl = sun_data["h_svetl"]
        day_of_week = dt_utc.isoweekday()
        ww = 0.0

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.source == "Open-Meteo-Archive",
            WeatherForecast.timestamp == dt_utc
        ).first()

        if existing:
            existing.temperature = temperatures[i]
            existing.cloud_cover = cloud_covers[i]
            existing.pressure = pressures[i]
            existing.humidity = humidities[i]
            existing.wind_speed = wind_speeds[i]
            existing.st_s = st_s
            existing.h_svetl = round(h_svetl, 6)
            existing.azimuth = round(azimuth, 6)
            existing.elevation = round(elevation, 6)
            existing.day_of_week = day_of_week
            existing.ww = ww
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temperatures[i],
                cloud_cover=cloud_covers[i],
                pressure=pressures[i],
                humidity=humidities[i],
                wind_speed=wind_speeds[i],
                source="Open-Meteo-Archive",
                st_s=st_s,
                h_svetl=round(h_svetl, 6),
                azimuth=round(azimuth, 6),
                elevation=round(elevation, 6),
                day_of_week=day_of_week,
                ww=ww
            )
            db.add(weather_record)
        saved_count += 1

    db.commit()
    return saved_count


def fetch_and_save_visual_crossing_weather(
    db: Session,
    station_id: int,
    target_date: Optional[date] = None,
    api_key: Optional[str] = None
) -> int:
    """
    Завантажує погодинний прогноз погоди на обрану дату з Visual Crossing Timeline API
    та зберігає/оновлює його у Neon PostgreSQL базі даних разом із сонячними та астрономічними полями.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    key = api_key or VISUAL_CROSSING_API_KEY
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API ключ для Visual Crossing не налаштовано. Будь ласка, вкажіть VISUAL_CROSSING_API_KEY у .env або передайте api_key."
        )

    date_str = target_date.isoformat()
    url = f"{VISUAL_CROSSING_URL}/{station.latitude},{station.longitude}/{date_str}"
    params = {
        "unitGroup": "metric",
        "key": key,
        "contentType": "json",
        "include": "hours,days"
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недійсний або неавторизований API ключ Visual Crossing."
            )
        elif response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Вичерпано ліміт запитів Visual Crossing API."
            )
        response.raise_for_status()
        data = response.json()
    except HTTPException:
        raise
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Помилка підключення до сервісу погоди Visual Crossing: {str(e)}"
        )

    days_list = data.get("days", [])
    if not days_list:
        return 0

    hourly_items = days_list[0].get("hours", [])
    if not hourly_items:
        return 0

    saved_count = 0
    for hour_item in hourly_items:
        epoch = hour_item.get("datetimeEpoch")
        if epoch:
            dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
        else:
            time_parts = hour_item.get("datetime", "00:00:00").split(":")
            h = int(time_parts[0]) if len(time_parts) > 0 else 0
            dt_utc = datetime(target_date.year, target_date.month, target_date.day, h, 0, 0, tzinfo=timezone.utc)

        # Розраховуємо сонячні та астрономічні поля 1-в-1 з unit2.py
        sun_data = calculate_sun_position(station.latitude, station.longitude, dt_utc)
        azimuth = sun_data["azimuth"]
        elevation = sun_data["elevation"]
        st_s = sun_data["st_s"]
        h_svetl = sun_data["h_svetl"]
        day_of_week = dt_utc.isoweekday()
        ww = 0.0

        temperature = float(hour_item.get("temp", 0.0))
        cloud_cover = float(hour_item.get("cloudcover", 0.0))
        pressure = float(hour_item.get("pressure", 1013.25))
        humidity = float(hour_item.get("humidity", 50.0))
        # Visual Crossing в unitGroup=metric повертає windspeed в км/год -> переводимо в м/с
        wind_speed_raw = float(hour_item.get("windspeed", 0.0))
        wind_speed = round(wind_speed_raw / 3.6, 2)

        existing = db.query(WeatherForecast).filter(
            WeatherForecast.station_id == station_id,
            WeatherForecast.source == "Visual-Crossing",
            WeatherForecast.timestamp == dt_utc
        ).first()

        if existing:
            existing.temperature = temperature
            existing.cloud_cover = cloud_cover
            existing.pressure = pressure
            existing.humidity = humidity
            existing.wind_speed = wind_speed
            existing.source = "Visual-Crossing"
            existing.st_s = st_s
            existing.h_svetl = round(h_svetl, 6)
            existing.azimuth = round(azimuth, 6)
            existing.elevation = round(elevation, 6)
            existing.day_of_week = day_of_week
            existing.ww = ww
        else:
            weather_record = WeatherForecast(
                station_id=station_id,
                timestamp=dt_utc,
                temperature=temperature,
                cloud_cover=cloud_cover,
                pressure=pressure,
                humidity=humidity,
                wind_speed=wind_speed,
                source="Visual-Crossing",
                st_s=st_s,
                h_svetl=round(h_svetl, 6),
                azimuth=round(azimuth, 6),
                elevation=round(elevation, 6),
                day_of_week=day_of_week,
                ww=ww
            )
            db.add(weather_record)

        saved_count += 1

    db.commit()
    return saved_count

