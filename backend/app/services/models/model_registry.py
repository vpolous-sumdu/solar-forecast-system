"""
Реєстр моделей прогнозування сонячної генерації.
Тут можна легко додавати нові експериментальні моделі (V2, XGBoost, Transformer тощо)
поруч із непорушним Еталоном (Baseline 1:1).
"""
import numpy as np
from app.services.models.baseline.baseline_model import run_baseline_neural_forecast
from app.services.models.custom_v2.custom_model import run_v2_experimental_forecast

def execute_model_prediction(model_code: str, mas_in: np.ndarray, weights_dict: dict) -> np.ndarray:
    """
    Точка виклику моделі за її кодом.
    """
    if model_code == "baseline" or not model_code:
        return run_baseline_neural_forecast(mas_in, weights_dict)
    elif model_code == "v2_experimental":
        return run_v2_experimental_forecast(mas_in, weights_dict)
    
    # За замовчуванням виконуємо Еталон
    return run_baseline_neural_forecast(mas_in, weights_dict)
