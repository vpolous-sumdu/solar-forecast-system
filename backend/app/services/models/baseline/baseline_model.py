import numpy as np

def mapminmax_apply(x: np.ndarray, xoffset: np.ndarray, gain: np.ndarray, ymin: float = -1.0) -> np.ndarray:
    return (x - xoffset) * gain + ymin

def tansig_apply(n: np.ndarray) -> np.ndarray:
    return 2.0 / (1.0 + np.exp(-2.0 * n)) - 1.0

def mapminmax_reverse(y: np.ndarray, ymin: float, gain: float, xoffset: float) -> np.ndarray:
    return (y - ymin) / gain + xoffset

def run_baseline_neural_forecast(mas_in: np.ndarray, weights_dict: dict) -> np.ndarray:
    """
    Еталонне нейромережеве ядро (Baseline 1:1 Delphi/MATLAB).
    Приймає mas_in (7, Q) та ваги з БД.
    """
    x1_xoffset = np.array(weights_dict["xoffset"], dtype=np.float64).reshape(-1, 1)
    x1_gain = np.array(weights_dict["gain"], dtype=np.float64).reshape(-1, 1)
    x1_ymin = -1.0

    b1 = np.array(weights_dict["b1"], dtype=np.float64).reshape(-1, 1)
    IW1_1 = np.array(weights_dict["IW1_1"], dtype=np.float64)

    b2 = float(weights_dict["b2"])
    LW2_1 = np.array(weights_dict["LW2_1"], dtype=np.float64)

    y1_ymin = -1.0
    y1_gain = float(weights_dict["y_gain"])
    y1_xoffset = 0.0

    xp1 = mapminmax_apply(mas_in, x1_xoffset, x1_gain, x1_ymin)
    a1 = tansig_apply(b1 + np.dot(IW1_1, xp1))
    a2 = b2 + np.dot(LW2_1, a1)
    y1 = mapminmax_reverse(a2, y1_ymin, y1_gain, y1_xoffset)

    return y1.flatten()
