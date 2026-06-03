"""
Liveness detection (anti-spoofing) using MiniFASNet ONNX models.

Uses DUAL models (MiniFASNetV2 + MiniFASNetV1SE) with different scale factors
as designed by the original Silent-Face-Anti-Spoofing architecture. Each model
sees different amounts of surrounding context, and their averaged predictions
catch spoofs that a single model would miss.

Single-frame inference, fully offline, ~50ms per face (two models).
"""
import os
import logging
import numpy as np

from .config import CFG

logger = logging.getLogger(__name__)

# Try to import onnxruntime; if unavailable, liveness gracefully degrades
try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

# Dual-model configuration matching original Silent-Face-Anti-Spoofing
# Each model sees a different amount of surrounding context via scale factor
_MODEL_CONFIGS = [
    {"filename": "antispoof.onnx", "scale": 2.7, "name": "MiniFASNetV2"},
    {"filename": "antispoof_v1se.onnx", "scale": 4.0, "name": "MiniFASNetV1SE"},
]

# Output class index for "live/real" — verified from these ONNX exports
_LIVE_CLASS_INDEX = 2  # Output shape [batch, 3]: [spoof1, spoof2, live]


def _resolve_model_dir() -> str:
    """Resolve the models directory path."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "models"),
        os.path.join(os.path.dirname(__file__), "models"),
        os.path.abspath("models"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return os.path.abspath(path)
    return os.path.abspath("models")


def _softmax(x: np.ndarray) -> np.ndarray:
    """Compute softmax along the last axis."""
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / e_x.sum(axis=-1, keepdims=True)


def _crop_face(frame: np.ndarray, bbox: tuple, scale: float, out_size: tuple) -> np.ndarray:
    """
    Crop face region from frame matching the original Silent-Face-Anti-Spoofing.

    The original code clamps the CENTER (not just the boundaries) to ensure
    the crop is always square and fully inside the frame. This is important
    for faces near edges.

    Args:
        frame: Full BGR frame.
        bbox: Face bounding box as (x1, y1, x2, y2).
        scale: Context expansion factor (2.7 for V2, 4.0 for V1SE).
        out_size: Output (height, width) tuple.
    """
    import cv2

    src_h, src_w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    box_w = x2 - x1
    box_h = y2 - y1

    # Scaled crop side length (square)
    scale_tmp = max(box_w, box_h) * scale

    # Compute center, then clamp it so the full crop fits inside the frame
    # (this matches the original Silent-Face-Anti-Spoofing crop logic)
    center_x = x1 + box_w / 2.0
    center_y = y1 + box_h / 2.0
    center_x = max(scale_tmp / 2, center_x)
    center_y = max(scale_tmp / 2, center_y)
    center_x = min(src_w - scale_tmp / 2, center_x)
    center_y = min(src_h - scale_tmp / 2, center_y)

    # Crop boundaries
    crop_x1 = max(0, int(center_x - scale_tmp / 2))
    crop_y1 = max(0, int(center_y - scale_tmp / 2))
    crop_x2 = min(src_w, int(center_x + scale_tmp / 2))
    crop_y2 = min(src_h, int(center_y + scale_tmp / 2))

    cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
    out_h, out_w = out_size
    return cv2.resize(cropped, (out_w, out_h))


class LivenessChecker:
    """
    Anti-spoofing liveness checker using dual MiniFASNet ONNX models.

    Uses both MiniFASNetV2 (scale 2.7) and MiniFASNetV1SE (scale 4.0)
    and averages their softmax predictions, matching the original
    Silent-Face-Anti-Spoofing design.

    Usage:
        checker = LivenessChecker()
        result = checker.check(frame, bbox)
        # result = {"is_live": True, "score": 0.95}
    """

    def __init__(self):
        self._models = []  # List of (session, input_name, input_size, scale, name)
        self._loaded = False

        if not CFG.LIVENESS_ENABLED:
            logger.info("[liveness] Liveness detection disabled by config")
            return

        if not HAS_ORT:
            logger.warning(
                "[liveness] onnxruntime not installed — liveness check will always pass. "
                "Install with: pip install onnxruntime"
            )
            return

        model_dir = _resolve_model_dir()

        for cfg in _MODEL_CONFIGS:
            # Allow explicit override for single-model path
            if CFG.LIVENESS_MODEL_PATH and cfg["filename"] == "antispoof.onnx":
                model_path = CFG.LIVENESS_MODEL_PATH
            else:
                model_path = os.path.join(model_dir, cfg["filename"])

            if not os.path.isfile(model_path):
                logger.warning(
                    f"[liveness] Model not found: {cfg['name']} ({model_path})"
                )
                continue

            try:
                session = ort.InferenceSession(
                    model_path,
                    providers=["CPUExecutionProvider"],
                )
                input_meta = session.get_inputs()[0]
                input_name = input_meta.name

                # Read input size dynamically
                input_size = (80, 80)
                if len(input_meta.shape) == 4:
                    h, w = input_meta.shape[2], input_meta.shape[3]
                    if isinstance(h, int) and isinstance(w, int):
                        input_size = (h, w)

                self._models.append((session, input_name, input_size, cfg["scale"], cfg["name"]))
                logger.info(f"[liveness] Loaded {cfg['name']} (scale={cfg['scale']}, input={input_size[0]}x{input_size[1]})")

            except Exception as e:
                logger.error(f"[liveness] Failed to load {cfg['name']}: {e}")

        if self._models:
            self._loaded = True
            names = ", ".join(name for _, _, _, _, name in self._models)
            print(f"[liveness] Anti-spoof loaded: {names} ({len(self._models)} model(s))")
        else:
            logger.warning(
                "[liveness] No anti-spoof models found — liveness check will always pass. "
                "Run: python main.py download-models --antispoof"
            )

    def check(self, frame: np.ndarray, bbox: tuple) -> dict:
        """
        Check if a face is live (real) or spoofed.

        Runs all loaded models with their respective scale factors and
        averages the softmax predictions (matching original architecture).

        Args:
            frame: Full BGR frame from camera.
            bbox: Face bounding box as (x1, y1, x2, y2).

        Returns:
            dict with "is_live" (bool) and "score" (float 0-1, higher = more live).
        """
        # Graceful fallback when models aren't available
        if not self._loaded or not self._models:
            return {"is_live": True, "score": 0.51}

        try:
            import cv2

            # Accumulate softmax predictions across all models
            prediction = np.zeros((1, 3))
            n_models = 0

            for session, input_name, input_size, scale, name in self._models:
                # Crop with model-specific scale factor
                face_crop = _crop_face(frame, bbox, scale, input_size)

                if face_crop.size == 0:
                    continue

                # Preprocess: BGR->RGB -> float32 -> /255 -> CHW -> batch
                rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                blob = rgb.astype(np.float32) / 255.0
                blob = blob.transpose(2, 0, 1)  # HWC -> CHW
                blob = np.expand_dims(blob, axis=0)  # Add batch dim

                # Run ONNX inference
                outputs = session.run(None, {input_name: blob})
                logits = outputs[0]  # Shape: [1, 3]

                # Softmax and accumulate
                probs = _softmax(logits)
                prediction += probs
                n_models += 1

            if n_models == 0:
                return {"is_live": True, "score": 0.51}

            # Average predictions across models
            avg_probs = prediction / n_models
            live_score = float(avg_probs[0][_LIVE_CLASS_INDEX])

            is_live = live_score >= CFG.LIVENESS_THRESHOLD

            if CFG.LOG_LIVENESS:
                status = "LIVE" if is_live else "SPOOF"
                logger.debug(
                    f"[liveness] {status} (score: {live_score:.3f}, "
                    f"probs: [{avg_probs[0][0]:.3f}, {avg_probs[0][1]:.3f}, {avg_probs[0][2]:.3f}])"
                )

            return {"is_live": is_live, "score": live_score}

        except Exception as e:
            logger.error(f"[liveness] Inference error: {e}")
            # On error, fail-open (allow through) to avoid blocking real users
            return {"is_live": True, "score": 0.51}
