"""
Download and manage InsightFace model packs.
"""
try:
    from insightface.app import FaceAnalysis
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False

from .config import CFG


def download_models(model_name: str = None):
    """
    Pre-download InsightFace model to avoid runtime delays.
    """
    if not HAS_INSIGHTFACE:
        print("[packs] ⚠️  InsightFace not installed")
        print("[packs] Install with: pip install insightface")
        print("[packs] Using OpenCV cascade classifier fallback")
        return

    model = model_name or CFG.MODEL_NAME
    print(f"[packs] Downloading model: {model}")
    try:
        app = FaceAnalysis(name=model)
        app.prepare(ctx_id=0, det_size=CFG.DET_SIZE)
        print(f"[packs] Model {model} ready")
    except Exception as e:
        print(f"[packs] Error: {e}")
        raise


def download_antispoof_models():
    """
    Pre-download anti-spoof models for liveness detection.
    """
    if not HAS_INSIGHTFACE:
        print("[packs] ⚠️  InsightFace not installed, cannot download anti-spoof models")
        return

    print("[packs] Ensuring anti-spoof models are available...")
    try:
        from insightface.app.face_antispoof import FaceAntiSpoof
        antispoof = FaceAntiSpoof()
        print("[packs] Anti-spoof models ready")
    except ImportError:
        print("[packs] ⚠️  Anti-spoof not available, will use default confidence 0.5")
    except Exception as e:
        print(f"[packs] Warning downloading anti-spoof: {e}")
