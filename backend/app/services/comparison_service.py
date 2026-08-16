from datetime import datetime, date, timezone
from typing import List, Dict, Optional, Any

from fastapi import HTTPException, status
from sqlalchemy import cast, Date
from sqlalchemy.orm import Session

from app.models.actual_generation import ActualGeneration
from app.models.generation import GenerationForecast
from app.models.station import Station
from app.models.weather import WeatherForecast
from app.services.actual_generation_service import get_or_sync_actual_generation


def get_available_comparison_dates(db: Session, station_id: int) -> List[str]:
    """
    Повертає список унікальних дат (YYYY-MM-DD), для яких є прогнози або фактичні дані в БД.
    """
    forecast_dates = db.query(cast(GenerationForecast.timestamp, Date)).filter(
        GenerationForecast.station_id == station_id
    ).distinct().all()

    actual_dates = db.query(cast(ActualGeneration.timestamp, Date)).filter(
        ActualGeneration.station_id == station_id
    ).distinct().all()

    all_dates = set()
    for d in forecast_dates:
        if d[0]:
            all_dates.add(d[0].isoformat())
    for d in actual_dates:
        if d[0]:
            all_dates.add(d[0].isoformat())

    sorted_dates = sorted(list(all_dates), reverse=True)
    return sorted_dates


def compare_forecast_and_actual_for_date(
        db: Session,
        station_id: int,
        target_date: date,
        weather_source: str = "OpenWeatherMap",
        model_id: Optional[int] = None,
        force_sync_actual: bool = False
) -> Dict[str, Any]:
    """
    Виконує погодинне зіставлення прогнозу (з generation_forecasts) та факту (з actual_generations)
    та розраховує еталонні метрики дисертації 1-в-1 з Delphi/Python baseline (compare_unit.py).
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    # 1. Отримуємо збережені прогнози генерації за обрану дату, джерело погоди та модель
    start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    gen_query = db.query(GenerationForecast, WeatherForecast).outerjoin(
        WeatherForecast,
        (GenerationForecast.station_id == WeatherForecast.station_id) &
        (GenerationForecast.timestamp == WeatherForecast.timestamp) &
        (GenerationForecast.weather_source == WeatherForecast.source)
    ).filter(
        GenerationForecast.station_id == station_id,
        GenerationForecast.weather_source == weather_source,
        GenerationForecast.timestamp >= start_dt,
        GenerationForecast.timestamp <= end_dt
    )

    if model_id:
        gen_query = gen_query.filter(GenerationForecast.model_id == model_id)

    forecast_records = gen_query.order_by(GenerationForecast.timestamp.asc()).all()

    # Якщо прогнозу немає взагалі, НЕ завантажуємо факт з PVOutput і повертаємо статус has_forecast_data = False
    if not forecast_records:
        return {
            "station_id": station_id,
            "station_name": station.name,
            "date": target_date.isoformat(),
            "weather_source": weather_source,
            "has_forecast_data": False,
            "has_actual_data": False,
            "metrics": {
                "total_actual_kwh": 0.0,
                "total_forecast_kwh": 0.0,
                "total_delta_kwh": 0.0,
                "abs_error_kwh": 0.0,
                "relative_error_percent": 0.0
            },
            "hourly_data": [],
            "scientific_memo": "Немає прогнозу генерації для цієї дати."
        }

    # 2. Якщо прогноз є — отримуємо фактичну генерацію (з кешу БД або з PVOutput)
    actual_records = get_or_sync_actual_generation(
        db, station_id, target_date, force_sync=force_sync_actual
    )
    actual_map: Dict[int, ActualGeneration] = {}
    for r in actual_records:
        h = r.timestamp.hour
        actual_map[h] = r

    forecast_map: Dict[int, Dict[str, Any]] = {}
    for gen, w in forecast_records:
        h = gen.timestamp.hour
        forecast_map[h] = {
            "predicted_power_watts": gen.predicted_power_watts,
            "predicted_power_kw": gen.predicted_power_kw,
            "st_s": w.st_s if w else 0,
            "elevation": w.elevation if w else 0.0,
            "cloud_cover": w.cloud_cover if w else 0.0,
            "temperature": w.temperature if w else 0.0
        }

    # 3. Формуємо погодинне порівняння 00:00 - 23:00 1-в-1 з compare_unit.py
    hourly_comparison = []

    total_forecast_w = 0.0
    total_actual_w = 0.0
    sum_diff_w = 0.0  # Сума (Реал - Прогноз)

    separator = "     "
    memo_lines = [
        f"h_in{separator}h_fin{separator}Прогноз (Вт){separator}Реал (Вт){separator}Різниця (Вт)"
    ]

    for h in range(24):
        h_in = h
        h_fin = h + 1
        dt_hour = datetime(target_date.year, target_date.month, target_date.day, h, 0, 0, tzinfo=timezone.utc)

        # Прогноз для цієї години
        fc_data = forecast_map.get(h, None)
        p_f_w = float(fc_data["predicted_power_watts"]) if fc_data else 0.0
        p_f_kw = float(fc_data["predicted_power_kw"]) if fc_data else (p_f_w / 1000.0)
        st_s = fc_data["st_s"] if fc_data else (0 if h < 5 or h > 20 else 2)

        # Факт для цієї години
        act_rec = actual_map.get(h, None)
        p_r_w = float(act_rec.actual_power_watts) if act_rec else 0.0
        p_r_kw = float(act_rec.actual_power_kw) if act_rec else (p_r_w / 1000.0)

        # Погодинна різниця: diff = power_real - power_forecast (як у compare_unit.py)
        diff_w = p_r_w - p_f_w
        diff_kw = p_r_kw - p_f_kw
        abs_diff_kw = abs(diff_kw)

        total_forecast_w += p_f_w
        total_actual_w += p_r_w
        sum_diff_w += diff_w

        # Рядок для текстового звіту Memo1
        memo_lines.append(
            f"{h_in}{separator}{h_fin}{separator}{p_f_w:.2f}{separator}{p_r_w:.2f}{separator}{diff_w:.2f}")

        hourly_comparison.append({
            "hour": h,
            "timestamp": dt_hour,
            "forecast_watts": round(p_f_w, 2),
            "forecast_kw": round(p_f_kw, 4),
            "actual_watts": round(p_r_w, 2),
            "actual_kw": round(p_r_kw, 4),
            "delta_watts": round(diff_w, 2),
            "delta_kw": round(diff_kw, 4),
            "abs_delta_kw": round(abs_diff_kw, 4),
            "st_s": st_s
        })

    # 4. Розрахунок еталонних сумарних метрик (1-в-1 з compare_unit.py)
    total_forecast_kwh = total_forecast_w / 1000.0
    total_actual_kwh = total_actual_w / 1000.0
    total_delta_kwh = sum_diff_w / 1000.0

    # err_abs = abs(sum_diff)
    abs_error_kwh = abs(total_delta_kwh)

    # rel_err_percent = (abs_error / total_actual) * 100.0
    relative_error_percent = 0.0
    if total_actual_kwh > 0:
        relative_error_percent = (abs_error_kwh / total_actual_kwh) * 100.0

    memo_lines.append("")
    memo_lines.append(f"Сумарна реальна (кВт) = {total_actual_kwh:.2f}")
    memo_lines.append(f"Абсолютна похибка (кВт) = {abs_error_kwh:.2f}")
    memo_lines.append(f"Відносна похибка (%) = {relative_error_percent:.2f}%")

    memo_text = "\n".join(memo_lines)

    return {
        "station_id": station_id,
        "station_name": station.name,
        "date": target_date.isoformat(),
        "weather_source": weather_source,
        "has_forecast_data": len(forecast_records) > 0,
        "has_actual_data": len(actual_records) > 0,
        "metrics": {
            "total_actual_kwh": round(total_actual_kwh, 2),
            "total_forecast_kwh": round(total_forecast_kwh, 2),
            "total_delta_kwh": round(total_delta_kwh, 2),
            "abs_error_kwh": round(abs_error_kwh, 2),
            "relative_error_percent": round(relative_error_percent, 2)
        },
        "hourly_data": hourly_comparison,
        "scientific_memo": memo_text
    }
