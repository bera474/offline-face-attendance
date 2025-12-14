import datetime as dt
import numpy as np


ISO = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_utc_iso() -> str:
    return dt.datetime.utcnow().strftime(ISO)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    an = np.linalg.norm(a) + 1e-9
    bn = np.linalg.norm(b) + 1e-9
    return float(np.dot(a, b) / (an * bn))