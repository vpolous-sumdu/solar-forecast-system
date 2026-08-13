import os
import urllib.request
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.station import Station

load_dotenv()

# Усі 12 еталонних станцій із PVOutput та python_forecasting_system
BASELINE_STATIONS = [
    "68459", "72282", "77407", "77586", "77587", "77588",
    "77589", "77590", "77591", "78440", "78441", "78444"
]

PVOUTPUT_KEY = "essolar"

def fetch_station_from_pvoutput(station_id: str) -> dict:
    """Отримує точні живі дані станції напряму з PVOutput API"""
    url = f"https://pvoutput.org/service/r2/getsystem.jsp?sid={station_id}&key={PVOUTPUT_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode("utf-8").strip()
        parts = data.split(",")
        name = parts[0] if len(parts) > 0 else f"СЕС #{station_id}"
        cap_w = float(parts[1]) if len(parts) > 1 and parts[1] else 30000.0
        lat = float(parts[13]) if len(parts) > 13 and parts[13] else 50.9
        lon = float(parts[14]) if len(parts) > 14 and parts[14] else 34.8
        
        return {
            "id": int(station_id),
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "installed_capacity_kw": round(cap_w / 1000.0, 2) # Конвертуємо Вт у кВт
        }

def seed_and_sync_stations():
    """Синхронізує всі 12 станцій з PVOutput у базу Neon PostgreSQL"""
    db: Session = SessionLocal()
    print("--------------------------------------------------")
    print("🌐 Синхронізація 12 справжніх СЕС з PVOutput -> Neon DB...")
    print("--------------------------------------------------")
    
    count_added = 0
    count_updated = 0
    
    try:
        for sid in BASELINE_STATIONS:
            print(f"📡 Запит до PVOutput API для станції ID {sid}...")
            st_data = fetch_station_from_pvoutput(sid)
            
            station = db.query(Station).filter(Station.id == st_data["id"]).first()
            if not station:
                station = Station(
                    id=st_data["id"],
                    name=st_data["name"],
                    latitude=st_data["latitude"],
                    longitude=st_data["longitude"],
                    installed_capacity_kw=st_data["installed_capacity_kw"]
                )
                db.add(station)
                count_added += 1
                print(f"   ➕ Додано: {st_data['name']} ({st_data['installed_capacity_kw']} кВт)")
            else:
                station.name = st_data["name"]
                station.latitude = st_data["latitude"]
                station.longitude = st_data["longitude"]
                station.installed_capacity_kw = st_data["installed_capacity_kw"]
                count_updated += 1
                print(f"   🔄 Оновлено: {st_data['name']} ({st_data['installed_capacity_kw']} кВт)")
                
        db.commit()
        print("--------------------------------------------------")
        print(f"🎉 УСПІШНО! Додано нових: {count_added}, Оновлено/Синхронізовано: {count_updated}")
        print("--------------------------------------------------")
        return {"added": count_added, "updated": count_updated, "total": count_added + count_updated}
    except Exception as e:
        db.rollback()
        print(f"❌ Помилка: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_and_sync_stations()
