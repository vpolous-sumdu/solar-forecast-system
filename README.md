# ☀️ Solar Forecast System

## Інфраструктура

* **Frontend:** [Vercel](https://vercel.com)
* **Backend:** [Render](https://solar-forecast-system.onrender.com) (API Docs: [solar-forecast-system.onrender.com/docs](https://solar-forecast-system.onrender.com/docs))
* **Database:** [Neon](https://neon.tech)

> **Режим сну:** Через особливості безкоштовного тарифу Render бекенд засинає після 15 хвилин неактивності. Перший запит після простою може займати до 1 хвилини.

## Технологічний стек

* **Backend:** Python 3.12+, FastAPI
* **Frontend:** Angular 22.x
* **Database:** PostgreSQL 16+

## Структура бази даних

```mermaid
erDiagram
    stations ||--o{ weather_forecasts : "1:N (station_id)"
    stations ||--o{ neural_models : "1:N (station_id)"
    stations ||--o{ actual_generations : "1:N (station_id)"
    stations ||--o{ generation_forecasts : "1:N (station_id)"
    neural_models ||--o{ generation_forecasts : "1:N (model_id)"

    stations {
        int id PK "PVOutput System ID"
        string name "Назва станції"
        float latitude "Широта (WGS84)"
        float longitude "Довгота (WGS84)"
        float installed_capacity_kw "Встановлена потужність (кВт)"
        timestamptz created_at "Час створення"
    }

    weather_forecasts {
        int id PK "Унікальний ID"
        int station_id FK "ID станції -> stations.id"
        timestamptz timestamp "Дата та час години (UTC)"
        string source "OpenWeatherMap / Open-Meteo / Visual-Crossing"
        float temperature "Температура (°C)"
        float cloud_cover "Хмарність (%)"
        float pressure "Атмосферний тиск (гПа)"
        float humidity "Вологість (%)"
        float wind_speed "Швидкість вітру (м/с)"
        float elevation "Висота сонця над горизонтом (°)"
        float azimuth "Азимут сонця (°)"
        int st_s "Стан доби: 0-Ніч, 1-Сутінки, 2-День"
        float h_svetl "Частка світлого часу (0.0..1.0)"
        int day_of_week "День тижня (1-7)"
        float ww "Код погодних явищ WMO"
    }

    neural_models {
        int id PK "Унікальний ID моделі"
        int station_id FK "ID станції -> stations.id"
        string name "Назва моделі (напр. MATLAB_Baseline_v1.0)"
        string code "Системний код (baseline / custom_v2)"
        json weights "Матриці ваг та коефіцієнти нормалізації"
        timestamptz created_at "Час створення"
    }

    actual_generations {
        int id PK "Унікальний ID факту"
        int station_id FK "ID станції -> stations.id"
        timestamptz timestamp "Дата та час години (UTC)"
        float actual_power_kw "Фактична потужність (кВт)"
        float actual_power_watts "Фактична потужність (Вт)"
        timestamptz created_at "Час імпорту з PVOutput"
    }

    generation_forecasts {
        int id PK "Унікальний ID прогнозу"
        int station_id FK "ID станції -> stations.id"
        int model_id FK "ID моделі -> neural_models.id"
        timestamptz timestamp "Дата та час години (UTC)"
        string weather_source "Джерело погоди розрахунку"
        float predicted_power_kw "Прогнозована потужність (кВт)"
        float predicted_power_watts "Прогнозована потужність (Вт)"
        timestamptz created_at "Час розрахунку"
    }
```
