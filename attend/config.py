import os
from dataclasses import dataclass


@dataclass
class Config:
    # Paths
    DB_PATH: str = os.environ.get("ATTEND_DB", os.path.abspath("attendance.db"))
    MODEL_NAME: str = os.environ.get("ATTEND_MODEL", "buffalo_l")  # InsightFace pack
    DATASET_DIR: str = os.environ.get("ATTEND_DATASET", os.path.abspath("dataset"))

    # Recognition thresholds (cosine similarity)
    SIM_THRESHOLD: float = float(os.environ.get("ATTEND_SIM_THRESHOLD", 0.60))
    REARM_SECONDS: float = float(os.environ.get("ATTEND_REARM", 15))

    # Video
    CAMERA_INDEX: int = int(os.environ.get("ATTEND_CAM", 0))
    DET_SIZE: tuple[int, int] = (640, 640)
    FRAME_WIDTH: int = int(os.environ.get("ATTEND_WIDTH", 1280))
    FRAME_HEIGHT: int = int(os.environ.get("ATTEND_HEIGHT", 720))

    # UI
    WINDOW_NAME: str = "Smart Attendance (Offline)"
    SHOW_CONFIDENCE: bool = True
    LOG_MATCHES: bool = True

    # Packs
    PACK_MODEL_TAG: str = "insightface_512d"


CFG = Config()