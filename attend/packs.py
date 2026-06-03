"""
Download and manage InsightFace model packs and anti-spoof models.
"""
import os
import logging

try:
    from insightface.app import FaceAnalysis
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False

from .config import CFG

logger = logging.getLogger(__name__)

# Anti-spoof ONNX model download URLs (yakhyo MiniFASNet models, ~1.7MB each)
# Both models are needed: V2 (scale 2.7) + V1SE (scale 4.0)
ANTISPOOF_MODELS = [
    {
        "url": "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx",
        "filename": "antispoof.onnx",
        "name": "MiniFASNetV2",
    },
    {
        "url": "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV1SE.onnx",
        "filename": "antispoof_v1se.onnx",
        "name": "MiniFASNetV1SE",
    },
]
ANTISPOOF_MODEL_DIR = os.path.abspath("models")


def download_models(model_name: str = None):
    """
    Pre-download InsightFace model to avoid runtime delays.
    """
    if not HAS_INSIGHTFACE:
        print("[packs] InsightFace not installed")
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


def _download_file(url: str, dest: str, name: str):
    """Download a single file with progress reporting."""
    import urllib.request

    def _report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            print(f"\r[packs]   {name}: {pct:.0f}% ({downloaded // 1024} KB)", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=_report)
    print()  # Newline after progress


def download_antispoof_model():
    """
    Download both MiniFASNet ONNX models for liveness detection.

    Downloads MiniFASNetV2 (~1.7MB) and MiniFASNetV1SE (~1.7MB) from
    yakhyo/face-anti-spoofing GitHub releases. Both models are needed
    for reliable anti-spoofing (different scale factors catch different spoof types).

    One-time internet connection required. After that, everything works offline.
    """
    os.makedirs(ANTISPOOF_MODEL_DIR, exist_ok=True)

    for model_cfg in ANTISPOOF_MODELS:
        dest = os.path.join(ANTISPOOF_MODEL_DIR, model_cfg["filename"])
        name = model_cfg["name"]

        # Check if already exists
        if os.path.isfile(dest):
            size_kb = os.path.getsize(dest) / 1024
            print(f"[packs] {name} already exists ({size_kb:.0f} KB)")
            continue

        print(f"[packs] Downloading {name}...")
        try:
            _download_file(model_cfg["url"], dest, name)
            size_kb = os.path.getsize(dest) / 1024
            print(f"[packs] {name} downloaded OK ({size_kb:.0f} KB)")
        except Exception as e:
            print(f"\n[packs] ERROR: Failed to download {name}: {e}")
            print(f"[packs]   URL: {model_cfg['url']}")
            print(f"[packs]   Place it at: {dest}")
            # Clean up partial download
            if os.path.isfile(dest):
                os.remove(dest)
            raise

    print("[packs] Anti-spoof models ready")

