import os
from dataclasses import dataclass


@dataclass
class Config:
    # Paths
    DB_PATH: str = os.environ.get("ATTEND_DB", os.path.abspath("attendance.db"))
    MODEL_NAME: str = os.environ.get("ATTEND_MODEL", "buffalo_l")  # InsightFace pack
    DATASET_DIR: str = os.environ.get("ATTEND_DATASET", os.path.abspath("dataset"))

    # Recognition thresholds (cosine similarity)
    SIM_THRESHOLD: float = float(os.environ.get("ATTEND_SIM_THRESHOLD", 0.80))
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

    # Face Quality Thresholds (relaxed for low-light & low-quality cameras)
    QUALITY_MIN_FACE_SIZE: float = float(os.environ.get("ATTEND_QUALITY_MIN_SIZE", "0.01"))
    QUALITY_MIN_BLUR_SCORE: float = float(os.environ.get("ATTEND_QUALITY_MIN_BLUR", "20"))
    QUALITY_MIN_BRIGHTNESS: float = float(os.environ.get("ATTEND_QUALITY_MIN_BRIGHT", "15"))
    QUALITY_MAX_BRIGHTNESS: float = float(os.environ.get("ATTEND_QUALITY_MAX_BRIGHT", "245"))
    QUALITY_MAX_YAW: float = float(os.environ.get("ATTEND_QUALITY_MAX_YAW", "40"))
    QUALITY_MAX_PITCH: float = float(os.environ.get("ATTEND_QUALITY_MAX_PITCH", "40"))
    QUALITY_MAX_ROLL: float = float(os.environ.get("ATTEND_QUALITY_MAX_ROLL", "30"))
    QUALITY_ACCEPT_THRESHOLD: float = float(os.environ.get("ATTEND_QUALITY_THRESHOLD", "0.20"))

    # Packs
    PACK_MODEL_TAG: str = "insightface_512d"

    # Liveness / Anti-Spoofing
    LIVENESS_ENABLED: bool = os.environ.get("ATTEND_LIVENESS", "1") == "1"
    LIVENESS_THRESHOLD: float = float(os.environ.get("ATTEND_LIVENESS_THRESHOLD", "0.8"))
    LIVENESS_MODEL_PATH: str = os.environ.get("ATTEND_LIVENESS_MODEL", "")  # auto-resolved
    LOG_LIVENESS: bool = os.environ.get("ATTEND_LOG_LIVENESS", "1") == "1"


CFG = Config()