# Liveness Detection (Anti-Spoofing) Integration

Add Silent-Face Anti-Spoofing (MiniFASNet) liveness detection to prevent photo/screen-based attendance fraud. Single-frame, fully offline, ~30ms per face.

## Proposed Changes

### Config
#### [MODIFY] [config.py](file:///d:/Coding/cf/offline-face-attendance/attend/config.py)
Add liveness settings:
```python
# Liveness / Anti-Spoofing
LIVENESS_ENABLED: bool = os.environ.get("ATTEND_LIVENESS", "1") == "1"
LIVENESS_THRESHOLD: float = float(os.environ.get("ATTEND_LIVENESS_THRESHOLD", "0.5"))
LIVENESS_MODEL_PATH: str = os.environ.get("ATTEND_LIVENESS_MODEL", "")  # auto-resolved
LOG_LIVENESS: bool = os.environ.get("ATTEND_LOG_LIVENESS", "1") == "1"
```

---

### Liveness Module
#### [NEW] [liveness.py](file:///d:/Coding/cf/offline-face-attendance/attend/liveness.py)

New module that:
1. Loads a MiniFASNet ONNX model (quantized, ~600KB)
2. Preprocesses: crop face with 2.7x scale padding → resize to 128×128 → float32 → CHW → batch
3. Runs ONNX inference → softmax → returns liveness score (0-1)
4. Provides `LivenessChecker` class with `check(frame, bbox) → {"is_live": bool, "score": float}`

**Key design decisions:**
- **Scale factor 2.7x** on the bounding box crop — this is critical for MiniFASNet accuracy, as it needs surrounding context (ears, chin, background) to detect flat surfaces
- **Input size read from ONNX model** dynamically — future-proof if model is swapped
- **Graceful fallback** — if model file is missing, liveness check returns `(True, 0.5)` and logs a warning (system still works without it)

---

### Model Download
#### [MODIFY] [packs.py](file:///d:/Coding/cf/offline-face-attendance/attend/packs.py)

Add `download_antispoof_model()` that downloads the pre-trained quantized ONNX model from the facenox/face-antispoof-onnx GitHub release to `models/antispoof.onnx`.

> [!IMPORTANT]
> This requires a one-time internet connection to download the ~600KB model. After that, everything works offline.

---

### App Integration
#### [MODIFY] [app.py](file:///d:/Coding/cf/offline-face-attendance/attend/app.py)

Insert liveness check into the main attendance loop, **between** face detection and face matching:

```
Current:  Detect Face → Match → Mark Attendance
New:      Detect Face → Liveness Check → Match → Mark Attendance
                         ↓ (if spoof)
                    Show "SPOOF" in red, skip matching
```

Changes:
- Import `LivenessChecker` 
- Initialize `LivenessChecker` in `AttendanceSystem.__init__`
- In the main loop, after detecting a face:
  - If `CFG.LIVENESS_ENABLED`: call `liveness_checker.check(frame, bbox)`
  - If `not is_live`: draw red "SPOOF" label, skip matching entirely
  - If `is_live`: proceed to matching as before
- Store `liveness_score` in attendance record (column already exists in DB)

#### [MODIFY] [attendance.py](file:///d:/Coding/cf/offline-face-attendance/attend/attendance.py)
Update `mark_attendance()` to accept and store `liveness_score` parameter (the column already exists in the schema).

---

### CLI Updates
#### [MODIFY] [cli.py](file:///d:/Coding/cf/offline-face-attendance/attend/cli.py)
Update the `download-models --antispoof` command to use the new download function.

---

## Open Questions

> [!IMPORTANT]
> **Model source**: The facenox/face-antispoof-onnx repo has a 600KB quantized model (98.2% accuracy). Alternatively, the original minivision-ai Silent-Face repo has models but requires PyTorch conversion. I'll go with the facenox quantized ONNX model — are you okay with that?

> [!NOTE]
> **Disabling liveness**: You can always disable it with `ATTEND_LIVENESS=0 python main.py run` or by setting `LIVENESS_ENABLED = False` in config.

## Verification Plan

### Manual Verification
1. Run `python main.py run` → show a real face → should mark attendance normally
2. Show a photo on phone screen → should display "SPOOF" in red, NOT mark attendance
3. Run with `ATTEND_LIVENESS=0 python main.py run` → should skip liveness check entirely
4. Run without the model file → should gracefully fall back (warn but still work)
