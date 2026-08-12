import numpy as np
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.station import Station
from app.models.weather import WeatherForecast
from app.models.neural_model import NeuralModel
from app.models.generation import GenerationForecast
from app.services.sun_service import calculate_sun_position

def _tansig(x: np.ndarray) -> np.ndarray:
    return 2.0 / (1.0 + np.exp(-2.0 * np.clip(x, -50.0, 50.0))) - 1.0


def _mapminmax_apply(x: np.ndarray, xoffset: np.ndarray, gain: np.ndarray, ymin: float = -1.0) -> np.ndarray:
    return (x - xoffset) * gain + ymin

def _mapminmax_reverse(y: np.ndarray, ymin: float, gain: float, xoffset: float) -> np.ndarray:
    return (y - ymin) / gain + xoffset

def generate_power_forecast(db: Session, station_id: int) -> List[GenerationForecast]:
    """
    Генерує та зберігає в базі прогнозовану потужність генерації (кВт)
    на основі погоди, сонячних кутів та ваг еталонної нейромережі.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    # 1. Завантажуємо активну модель з вагами з Neon DB
    model = db.query(NeuralModel).filter(
        NeuralModel.station_id == station_id,
        NeuralModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Активну нейромережеву модель для станції #{station_id} не знайдено в базі даних."
        )

    # 2. Завантажуємо збережену погоду
    weather_records = db.query(WeatherForecast).filter(
        WeatherForecast.station_id == station_id
    ).order_by(WeatherForecast.timestamp.asc()).all()

    if not weather_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Для станції #{station_id} немає завантаженого прогнозу погоди. Спочатку оновіть погоду з Open-Meteo."
        )

    # 3. Розпаковуємо ваги з JSON
    st_w = model.weights
    iw1_1 = np.array(st_w["IW1_1"], dtype=np.float64) # (30, 7)
    lw2_1 = np.array(st_w["LW2_1"], dtype=np.float64) # (1, 30)
    b1 = np.array(st_w["b1"], dtype=np.float64)       # (30, 1)
    b2 = float(st_w["b2"])
    xoffset = np.array(st_w["xoffset"], dtype=np.float64).reshape(-1, 1) # (7, 1)
    gain = np.array(st_w["gain"], dtype=np.float64).reshape(-1, 1)       # (7, 1)
    y_gain = float(st_w["y_gain"])

    results = []

    for w in weather_records:
        # Розраховуємо сонячну позицію з урахуванням місцевого часу та часового поясу (watch = 3.0 влітку)
        sun_pos = calculate_sun_position(station.latitude, station.longitude, w.timestamp, watch=3.0)
        
        # Код погодного явища WW (1.0 при значній хмарності >= 15%, 0.0 при ясній погоді - 1-в-1 з open_weather_map_unit.py)
        ww_val = 1.0 if w.cloud_cover >= 15.0 else 0.0

        # Сформований 7-вимірний вектор входів нейромережі 1-в-1 з еталоном:
        # [x1: st_s, x2: t, x3: h_svetl, x4: Nh, x5: AzSun, x6: Hsun, x7: WW]
        x_raw = np.array([
            [float(sun_pos["st_s"])],       # 1. st_s (0-ніч, 1-сутінки, 2-день)
            [float(w.temperature)],         # 2. t (температура)
            [float(sun_pos["h_svetl"])],    # 3. h_svetl інтервалу (0.0 ... 1.0)
            [float(w.cloud_cover)],         # 4. Nh (хмарність)
            [float(sun_pos["azimuth"])],    # 5. AzSun (азимут сонця)
            [float(sun_pos["elevation"])],  # 6. Hsun (висота сонця)
            [float(ww_val)]                 # 7. WW (коди погодних явищ)
        ], dtype=np.float64)


        if sun_pos["st_s"] == 0 or sun_pos["elevation"] <= -0.4:
            # Постпроцесинг 1-в-1 з for_forecast.py: якщо ніч або сонце низько під горизонтом (<= -0.4°) -> 0.0 кВт
            power_kw = 0.0

        else:
            # Прямий прохід двошарової нейромережі з MATLAB еталону:
            xp1 = _mapminmax_apply(x_raw, xoffset, gain, ymin=-1.0)
            a1 = _tansig(b1 + np.dot(iw1_1, xp1))
            a2 = b2 + np.dot(lw2_1, a1)
            power_w = _mapminmax_reverse(a2, ymin=-1.0, gain=y_gain, xoffset=0.0)[0, 0]
            
            # Переводимо з Ватт у кВт і обрізаємо від'ємні значення
            power_kw = float(max(0.0, round(power_w / 1000.0, 3)))


        # Оновлюємо або створюємо запис у базі
        existing = db.query(GenerationForecast).filter(
            GenerationForecast.station_id == station_id,
            GenerationForecast.timestamp == w.timestamp
        ).first()

        if existing:
            existing.predicted_power_kw = power_kw
            existing.model_id = model.id
            results.append(existing)
        else:
            gen_record = GenerationForecast(
                station_id=station_id,
                model_id=model.id,
                timestamp=w.timestamp,
                predicted_power_kw=power_kw
            )
            db.add(gen_record)
            results.append(gen_record)

    db.commit()
    return results
