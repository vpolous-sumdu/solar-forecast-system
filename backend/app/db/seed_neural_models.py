import sys
import os

# Додаємо шлях до суміжного еталонного проєкту python_forecasting_system
baseline_dir = "/Users/vladyslav/PycharmProjects/python_forecasting_system"
if baseline_dir not in sys.path:
    sys.path.append(baseline_dir)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.session import SessionLocal
from app.models.station import Station
from app.models.neural_model import NeuralModel

from MlToC.NF.station_weights import weights as baseline_weights


def seed_neural_models():
    """
    Заповнює таблицю neural_models точними вагами та параметрами
    нормалізації еталонної нейромережі з дисертації (station_weights.py).
    """
    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        if not stations:
            print("Помилка: Таблиця станцій порожня. Спочатку викличіть seed_stations.py")
            return

        seeded_count = 0
        for station in stations:
            st_id_str = str(station.id)
            if st_id_str not in baseline_weights:
                print(f"Попередження: Ваги для станції #{station.id} ({station.name}) не знайдено в station_weights.py")
                continue

            # Перевіряємо, чи є вже модель для цієї СЕС у базі
            existing_model = db.query(NeuralModel).filter(
                NeuralModel.station_id == station.id,
                NeuralModel.name == "MATLAB_Baseline_v1.0"
            ).first()

            station_weights = baseline_weights[st_id_str]

            if existing_model:
                existing_model.weights = station_weights
                existing_model.is_active = True
            else:
                new_model = NeuralModel(
                    station_id=station.id,
                    name="MATLAB_Baseline_v1.0",
                    is_active=True,
                    weights=station_weights
                )
                db.add(new_model)

            seeded_count += 1

        db.commit()
        print(f"Успішно заселено/оновлено ваги нейромереж для {seeded_count} сонячних станцій у Neon DB!")

    except Exception as e:
        db.rollback()
        print(f"Помилка при заповненні ваг нейромереж: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_neural_models()
