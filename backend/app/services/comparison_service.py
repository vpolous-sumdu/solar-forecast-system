import math
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
        weather_source: str = "ALL",
        model_id: Optional[int] = None,
        force_sync_actual: bool = False
) -> Dict[str, Any]:
    """
    Виконує погодинне зіставлення прогнозів (для всіх або вибраного джерела з generation_forecasts)
    та факту (з actual_generations) і розраховує еталонні метрики дисертації 1-в-1 з Delphi/Python baseline.
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
        GenerationForecast.timestamp >= start_dt,
        GenerationForecast.timestamp <= end_dt
    )

    if weather_source and weather_source.upper() != "ALL":
        gen_query = gen_query.filter(GenerationForecast.weather_source == weather_source)

    if model_id:
        gen_query = gen_query.filter(GenerationForecast.model_id == model_id)

    forecast_records = gen_query.order_by(GenerationForecast.timestamp.asc()).all()

    # Отримуємо фактичну генерацію (з кешу БД або з PVOutput)
    actual_records = get_or_sync_actual_generation(
        db, station_id, target_date, force_sync=force_sync_actual
    )
    actual_map: Dict[int, ActualGeneration] = {}
    total_actual_w = 0.0
    for r in actual_records:
        h = r.timestamp.hour
        actual_map[h] = r
        total_actual_w += float(r.actual_power_watts or 0.0)

    total_actual_kwh = total_actual_w / 1000.0

    # Визначаємо список доступних джерел прогнозу
    ordered_standard_sources = ["OpenWeatherMap", "Open-Meteo", "Visual-Crossing", "Open-Meteo-Archive"]
    found_sources = list(dict.fromkeys(r[0].weather_source for r in forecast_records if r[0].weather_source))
    available_sources = [s for s in ordered_standard_sources if s in found_sources] + [s for s in found_sources if
                                                                                       s not in ordered_standard_sources]

    # Якщо немає прогнозів і немає факту
    if not forecast_records and not actual_records:
        return {
            "station_id": station_id,
            "station_name": station.name,
            "date": target_date.isoformat(),
            "weather_source": weather_source,
            "has_forecast_data": False,
            "has_actual_data": False,
            "available_sources": [],
            "sources_metrics": {},
            "metrics": {
                "total_actual_kwh": 0.0,
                "total_forecast_kwh": 0.0,
                "total_delta_kwh": 0.0,
                "abs_error_kwh": 0.0,
                "relative_error_percent": 0.0,
                "mae_kw": 0.0,
                "rmse_kw": 0.0
            },
            "hourly_data": [],
            "scientific_memo": "Немає прогнозу генерації або фактичних даних для цієї дати."
        }

    # Мапимо прогнози: forecast_by_source[src][hour] = { predicted_power_watts, predicted_power_kw, st_s }
    forecast_by_source: Dict[str, Dict[int, Dict[str, Any]]] = {src: {} for src in available_sources}
    astro_by_hour: Dict[int, int] = {}

    for gen, w in forecast_records:
        src = gen.weather_source or "OpenWeatherMap"
        h = gen.timestamp.hour
        if src in forecast_by_source:
            forecast_by_source[src][h] = {
                "predicted_power_watts": float(gen.predicted_power_watts or 0.0),
                "predicted_power_kw": float(gen.predicted_power_kw or (
                    gen.predicted_power_watts / 1000.0 if gen.predicted_power_watts else 0.0)),
                "st_s": w.st_s if w else 0
            }
        if w and w.st_s is not None:
            astro_by_hour[h] = w.st_s

    # Розраховуємо метрики для кожного джерела
    sources_metrics: Dict[str, Dict[str, float]] = {}
    for src in available_sources:
        src_total_forecast_w = 0.0
        sum_diff_w = 0.0
        hourly_abs_diff_kw_list = []
        hourly_sq_diff_kw_list = []

        for h in range(24):
            fc_item = forecast_by_source[src].get(h)
            p_f_w = fc_item["predicted_power_watts"] if fc_item else 0.0
            p_f_kw = fc_item["predicted_power_kw"] if fc_item else 0.0

            act_item = actual_map.get(h)
            p_r_w = float(act_item.actual_power_watts) if act_item else 0.0
            p_r_kw = float(act_item.actual_power_kw) if act_item else 0.0

            diff_w = p_r_w - p_f_w
            diff_kw = p_r_kw - p_f_kw

            src_total_forecast_w += p_f_w
            sum_diff_w += diff_w

            hourly_abs_diff_kw_list.append(abs(diff_kw))
            hourly_sq_diff_kw_list.append(diff_kw ** 2)

        src_total_forecast_kwh = src_total_forecast_w / 1000.0
        src_total_delta_kwh = sum_diff_w / 1000.0
        src_abs_error_kwh = abs(src_total_delta_kwh)
        src_rel_error_percent = (src_abs_error_kwh / total_actual_kwh * 100.0) if total_actual_kwh > 0 else 0.0
        mae_kw = sum(hourly_abs_diff_kw_list) / 24.0
        rmse_kw = math.sqrt(sum(hourly_sq_diff_kw_list) / 24.0)

        sources_metrics[src] = {
            "total_actual_kwh": round(total_actual_kwh, 2),
            "total_forecast_kwh": round(src_total_forecast_kwh, 2),
            "total_delta_kwh": round(src_total_delta_kwh, 2),
            "abs_error_kwh": round(src_abs_error_kwh, 2),
            "relative_error_percent": round(src_rel_error_percent, 2),
            "mae_kw": round(mae_kw, 4),
            "rmse_kw": round(rmse_kw, 4)
        }

    # Формуємо 24-годинну таблицю зіставлення
    hourly_comparison = []
    primary_src = available_sources[0] if available_sources else "OpenWeatherMap"

    for h in range(24):
        dt_hour = datetime(target_date.year, target_date.month, target_date.day, h, 0, 0, tzinfo=timezone.utc)
        act_item = actual_map.get(h)
        p_r_w = float(act_item.actual_power_watts) if act_item else 0.0
        p_r_kw = float(act_item.actual_power_kw) if act_item else 0.0

        st_s = astro_by_hour.get(h, 0 if h < 5 or h > 20 else 2)

        sources_row: Dict[str, Dict[str, float]] = {}
        for src in available_sources:
            fc_item = forecast_by_source[src].get(h)
            p_f_w = fc_item["predicted_power_watts"] if fc_item else 0.0
            p_f_kw = fc_item["predicted_power_kw"] if fc_item else 0.0
            diff_w = p_r_w - p_f_w
            diff_kw = p_r_kw - p_f_kw

            sources_row[src] = {
                "forecast_watts": round(p_f_w, 2),
                "forecast_kw": round(p_f_kw, 4),
                "delta_watts": round(diff_w, 2),
                "delta_kw": round(diff_kw, 4),
                "abs_delta_kw": round(abs(diff_kw), 4)
            }

        # Первинне джерело для сумісності
        primary_data = sources_row.get(primary_src, {
            "forecast_watts": 0.0,
            "forecast_kw": 0.0,
            "delta_watts": round(p_r_w, 2),
            "delta_kw": round(p_r_kw, 4),
            "abs_delta_kw": round(abs(p_r_kw), 4)
        })

        hourly_comparison.append({
            "hour": h,
            "timestamp": dt_hour.isoformat(),
            "actual_watts": round(p_r_w, 2),
            "actual_kw": round(p_r_kw, 4),
            "st_s": st_s,
            "forecast_watts": primary_data["forecast_watts"],
            "forecast_kw": primary_data["forecast_kw"],
            "delta_watts": primary_data["delta_watts"],
            "delta_kw": primary_data["delta_kw"],
            "abs_delta_kw": primary_data["abs_delta_kw"],
            "sources": sources_row
        })

    # Створюємо підсумкові метрики (якщо обрано одне джерело або перше)
    primary_metrics = sources_metrics.get(primary_src, {
        "total_actual_kwh": round(total_actual_kwh, 2),
        "total_forecast_kwh": 0.0,
        "total_delta_kwh": round(total_actual_kwh, 2),
        "abs_error_kwh": round(total_actual_kwh, 2),
        "relative_error_percent": 100.0 if total_actual_kwh > 0 else 0.0,
        "mae_kw": 0.0,
        "rmse_kw": 0.0
    })

    return {
        "station_id": station_id,
        "station_name": station.name,
        "date": target_date.isoformat(),
        "weather_source": weather_source,
        "has_forecast_data": len(forecast_records) > 0,
        "has_actual_data": len(actual_records) > 0,
        "available_sources": available_sources,
        "sources_metrics": sources_metrics,
        "metrics": primary_metrics,
        "hourly_data": hourly_comparison,
        "scientific_memo": f"Сумарна реальна: {total_actual_kwh:.2f} кВт·год. Доступні прогнози: {', '.join(available_sources)}"
    }
