import urllib.request
import urllib.error
from datetime import datetime, date, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.station import Station
from app.models.actual_generation import ActualGeneration

PVOUTPUT_KEY = "essolar"

class TtmpRec:
    def __init__(self):
        self.d_str: str = ""
        self.t: str = ""
        self.gen: int = 0
        self.inst_power: int = 0
        self.av_power: int = 0
        self.hh: int = 0
        self.mm: int = 0
        self.energy_period: float = 0.0

def fetch_and_parse_pvoutput_for_date(station_id: int, target_date: date, capacity_limit_w: float = 50000.0) -> List[Dict]:
    """
    Завантажує фактичні дані з PVOutput API та виконує точну 1-в-1 обробку 
    та годинну агрегацію за алгоритмом із Delphi/Python baseline (unit5.py).
    Повертає 24 годинні записи (від 00:00 до 23:00) у Вт та кВт.
    """
    date_str = target_date.strftime("%Y%m%d")
    url = f"https://pvoutput.org/service/r2/getstatus.jsp?sid={station_id}&key={PVOUTPUT_KEY}&h=1&limit=808&asc=1&d={date_str}"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Embarcadero URI Client/1.0"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_content = response.read().decode("cp1251", errors="ignore")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Помилка завантаження фактичних даних з PVOutput для станції #{station_id} на дату {target_date}: {str(e)}"
        )
    
    # Розбиваємо відповідь на окремі записи за ';' або новим рядком
    raw_lines = [l.strip() for l in raw_content.replace("\n", ";").split(";") if l.strip()]
    
    requested_data = []
    for line in raw_lines:
        parts = [p.replace('"', '').strip() for p in line.split(',')]
        if len(parts) >= 2 and parts[0]:
            try:
                # Перевірка з Delphi: q := q div 10000000 (перевірка дати YYYYMMDD)
                q = int(parts[0]) // 10000000
            except ValueError:
                q = 0
            
            if q > 0 and len(parts) > 2:
                time_parts = parts[1].split(':')
                if len(time_parts) >= 2:
                    parts.extend([time_parts[0], time_parts[1]])
                    requested_data.append(parts)
                    
    # Створюємо масив проміжних об'єктів Ttmp_rec 1:1 з unit5.py
    tmp_rec_arr: List[TtmpRec] = []
    for parts in requested_data:
        rec = TtmpRec()
        rec.d_str = parts[0]
        rec.t = parts[1]
        try:
            rec.gen = int(parts[2])
        except (ValueError, IndexError):
            rec.gen = 0
        try:
            rec.inst_power = int(parts[4])
        except (ValueError, IndexError):
            rec.inst_power = 0
        try:
            rec.av_power = int(parts[5])
        except (ValueError, IndexError):
            rec.av_power = 0
        try:
            rec.hh = int(parts[-2])
            rec.mm = int(parts[-1])
        except (ValueError, IndexError):
            rec.hh = 0
            rec.mm = 0
        rec.energy_period = 0.0
        tmp_rec_arr.append(rec)
        
    # Розрахунок енергії за підінтервал (інтегрування потужності): energy_period = av_power * (h_curr - h_prev)
    for j in range(len(tmp_rec_arr)):
        if j == 0:
            tmp_rec_arr[j].energy_period = 0.0
        else:
            h_curr = tmp_rec_arr[j].hh + tmp_rec_arr[j].mm / 60.0
            h_prev = tmp_rec_arr[j-1].hh + tmp_rec_arr[j-1].mm / 60.0
            dt = max(0.0, h_curr - h_prev)
            # Якщо dt занадто велике (більше 2 годин, наприклад нічна перерва), обмежуємо
            if dt > 2.0:
                dt = 0.0
            tmp_rec_arr[j].energy_period = tmp_rec_arr[j].av_power * dt

    # Агрегування в 24 годинні інтервали (від 0 до 23)
    hourly_watts = {h: 0.0 for h in range(24)}
    
    for rec in tmp_rec_arr:
        h_fin = rec.hh + rec.mm / 60.0
        h_idx = int(h_fin)
        if 0 <= h_idx < 24:
            hourly_watts[h_idx] += rec.energy_period

    # Формуємо фінальний 24-годинний список
    results = []
    for h in range(24):
        p_w = hourly_watts[h]
        # Фільтрація за лімітом потужності СЕС
        if p_w > capacity_limit_w:
            p_w = capacity_limit_w
        if p_w < 0.0:
            p_w = 0.0
            
        dt_hour = datetime(target_date.year, target_date.month, target_date.day, h, 0, 0, tzinfo=timezone.utc)
        results.append({
            "hour": h,
            "timestamp": dt_hour,
            "actual_power_watts": round(float(p_w), 4),
            "actual_power_kw": round(float(p_w / 1000.0), 4)
        })
        
    return results

def get_or_sync_actual_generation(
    db: Session,
    station_id: int,
    target_date: date,
    force_sync: bool = False
) -> List[ActualGeneration]:
    """
    Отримує фактичну генерацію для СЕС за дату з кешу Neon PostgreSQL (Cache-Aside pattern).
    Якщо записів немає або force_sync=True, автоматично завантажує з PVOutput та зберігає в БД.
    """
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сонячну станцію з ID {station_id} не знайдено."
        )

    # Визначаємо встановлену потужність у Вт з запасом
    cap_limit_w = (station.installed_capacity_kw * 1000.0 * 1.5) if station.installed_capacity_kw else 50000.0

    start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    existing_records = db.query(ActualGeneration).filter(
        ActualGeneration.station_id == station_id,
        ActualGeneration.timestamp >= start_dt,
        ActualGeneration.timestamp <= end_dt
    ).order_by(ActualGeneration.timestamp.asc()).all()

    if existing_records and len(existing_records) == 24 and not force_sync:
        return existing_records

    # Якщо даних немає або викликано примусове оновлення (force_sync)
    parsed_hourly = fetch_and_parse_pvoutput_for_date(station_id, target_date, capacity_limit_w=cap_limit_w)
    
    saved_records = []
    for item in parsed_hourly:
        record = db.query(ActualGeneration).filter(
            ActualGeneration.station_id == station_id,
            ActualGeneration.timestamp == item["timestamp"]
        ).first()

        if record:
            record.actual_power_watts = item["actual_power_watts"]
            record.actual_power_kw = item["actual_power_kw"]
        else:
            record = ActualGeneration(
                station_id=station_id,
                timestamp=item["timestamp"],
                actual_power_watts=item["actual_power_watts"],
                actual_power_kw=item["actual_power_kw"]
            )
            db.add(record)
            
        saved_records.append(record)

    db.commit()
    return saved_records
