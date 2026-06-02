# Face Quality Scoring & Enrollment Validation - Implementation Summary

## What Was Implemented

### 1. New Quality Assessment Module (`attend/quality.py`)

Created a comprehensive face quality scoring system with 5 quality checks:

#### Functions:
- **`calculate_face_size(bbox, frame_shape)`** - Ensures face is 2-50% of frame
  - Feedback: "Face too small, move closer" or "Face too close, move back"

- **`estimate_face_angle(keypoints)`** - Detects head rotation using facial landmarks
  - Checks yaw (±15°), pitch (±15°), roll (±10°)
  - Feedback: "Head rotated X°, face camera" / "Head tilted, look straight ahead"

- **`detect_blur(face_roi)`** - Laplacian variance method for blur detection
  - Minimum sharpness: 100 (configurable)
  - Feedback: "Image too blurry, hold still"

- **`estimate_lighting(face_roi)`** - Brightness range check
  - Optimal range: 40-215 (middle brightness 128)
  - Feedback: "Too dark, improve lighting" or "Too bright, reduce lighting"

- **`overall_quality_score(bbox, keypoints, frame)`** - Combined score
  - Returns: `{"score": 0-1, "percentage": 0-100, "issues": [...], "passed": bool}`
  - Weighted average of all 4 checks
  - Requires >= 75% quality to pass (configurable)

---

### 2. Updated Configuration (`attend/config.py`)

Added 8 new configurable thresholds:

```python
QUALITY_MIN_FACE_SIZE = 0.02           # Min 2% of frame area
QUALITY_MIN_BLUR_SCORE = 100           # Laplacian variance threshold
QUALITY_MIN_BRIGHTNESS = 40            # Minimum brightness (0-255)
QUALITY_MAX_BRIGHTNESS = 215           # Maximum brightness (0-255)
QUALITY_MAX_YAW = 15                   # Max head rotation left/right (degrees)
QUALITY_MAX_PITCH = 15                 # Max head tilt up/down (degrees)
QUALITY_MAX_ROLL = 10                  # Max head rotation (degrees)
QUALITY_ACCEPT_THRESHOLD = 0.75        # Overall quality must be >= 75%
```

All configurable via environment variables (e.g., `ATTEND_QUALITY_THRESHOLD=0.80`)

---

### 3. Enhanced Enrollment Functions (`attend/enroll.py`)

#### `enroll_from_webcam()` - Real-time Quality Feedback
- **Live preview with quality score**: Shows "Quality: 82%" on-screen
- **Visual feedback**: Green box = good quality, Orange box = needs improvement
- **Specific guidance**: Displays issues like "Face too blurry" or "Too dark"
- **Quality-aware capture**: Only accepts captures >= 75% quality
- **Quality tracking**: Stores average quality of all captures in DB
- **Console output**: Logs each capture with quality percentage

#### `enroll_from_dataset()` - Batch Quality Filtering
- Scans all images in dataset directory
- Filters by quality automatically
- Shows `✓ accepted` and `✗ rejected` for each image
- Reports average quality of accepted faces
- Skips low-quality images automatically

#### `update_student_image()` - Re-enrollment with Validation
- Same quality checks as webcam enrollment
- Validates new captures before replacing old enrollment
- Stores actual quality score (was hardcoded as 1.0)

---

## Enrollment Workflow Changes

### Before:
```
User captures face → System accepts ANY detection → Stores in DB
Quality: Always 1.0 (hardcoded)
Accuracy: Poor (accepts blurry, dark, angled faces)
```

### After:
```
User captures face → System checks:
  ✓ Face size (2-50% of frame)
  ✓ Face angle (frontal, ±15° tolerance)
  ✓ Blur (sharp, Laplacian > 100)
  ✓ Lighting (brightness 40-215)
  ✓ Overall score >= 75%
→ If passed: Accept & show "Quality: 82%"
→ If failed: Reject & show specific reason

Quality: Actual score (0.75-1.0)
Accuracy: High (only accepts high-quality faces)
```

---

## Real-Time User Feedback

During enrollment, users see:
```
Video Feed with:
- Live quality percentage: "Quality: 82%"
- Visual indicators:
  ✓ Green box = ready to capture
  ✗ Orange box = quality needs improvement
- Specific issues: "Face too blurry" / "Too dark" / "Head rotated 18°, face camera"
- Capture counter: "Captures: 5/8"

Console Output:
[enroll-cam] Captured 1/8 (Quality: 87%)
[enroll-cam] Rejected (Quality: 62%) - Image too blurry, Hold still
[enroll-cam] Captured 2/8 (Quality: 91%)
...
[enroll-cam] Updated: John Doe (xyz-id) with 8 quality shots (avg quality: 0.87)
```

---

## Testing Instructions

### 1. Test Webcam Enrollment with Quality Checks:
```bash
python main.py enroll --name "TestStudent"
```
Expected behavior:
- See quality score on video (0-100%)
- Try blurry capture → "Image too blurry, hold still"
- Try dark capture → "Too dark, improve lighting"
- Try extreme angle → "Head rotated 25°, face camera"
- Accept only captures >= 75%

### 2. Test Dataset Enrollment with Quality Filtering:
```bash
# Create test dataset with good and bad images
mkdir -p dataset/TestUser
# Add some blurry, dark, and good quality photos

python main.py enroll-dataset dataset/
```
Expected behavior:
- Filters images automatically
- Shows `✓` for accepted, `✗` for rejected
- Only high-quality images used

### 3. Verify Quality Stored in Database:
```bash
sqlite3 attendance.db "SELECT s.name, e.quality FROM students s JOIN embeddings e ON s.id = e.student_id;"
```
Expected output:
```
TestStudent|0.87
TestUser|0.82
```
(No more hardcoded 1.0 values)

### 4. Test During Attendance Marking:
```bash
python main.py run
```
Expected behavior:
- High-quality enrollments recognized faster
- Fewer false positives (poor quality enrollments rejected during capture)
- More accurate matching

---

## Impact on System Accuracy

### Before:
- Any detected face = enrollment ❌
- Low-quality enrollments cause false matches ❌
- No quality audit trail ❌

### After:
- Only high-quality faces (75%+) = enrollment ✓
- Better enrollment quality = better recognition accuracy ✓
- Quality scores stored for audit trail ✓
- Real-time feedback guides users ✓

---

## Tuning Parameters

If you want more/less strict quality checks:

```bash
# Stricter quality requirements:
export ATTEND_QUALITY_THRESHOLD=0.85       # Require 85% quality (was 75%)
export ATTEND_QUALITY_MIN_BLUR=150         # More blur rejection (was 100)
export ATTEND_QUALITY_MAX_YAW=10           # Less head angle tolerance (was 15°)

# Looser quality requirements:
export ATTEND_QUALITY_THRESHOLD=0.60       # Accept 60% quality (was 75%)
export ATTEND_QUALITY_MIN_BLUR=50          # Less blur rejection (was 100)
export ATTEND_QUALITY_MAX_YAW=20           # More head angle tolerance (was 15°)
```

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `attend/quality.py` | NEW - Quality assessment module | 260 lines |
| `attend/config.py` | Added 8 quality thresholds | +14 lines |
| `attend/enroll.py` | Enhanced all 3 enrollment functions | +150 lines |

---

## Next Steps (Optional Enhancements)

1. **Enrollment history**: Store all capture attempts (passed/rejected) for analysis
2. **Multi-embedding storage**: Store top 3-5 embeddings per student (not just average)
3. **Recognition quality feedback**: Show quality score during attendance marking
4. **Similarity pre-check**: Warn if new enrollment is too similar to existing students
5. **Batch validation report**: Generate CSV of dataset quality statistics

---

## Summary

✅ **Quality Scoring**: 4-way assessment (size, angle, blur, lighting)
✅ **Real-time Feedback**: On-screen guidance during enrollment
✅ **Database Tracking**: Quality scores stored, not hardcoded
✅ **Configurable**: All thresholds adjustable via environment variables
✅ **No New Dependencies**: Uses only OpenCV + NumPy (already installed)
✅ **Improved Accuracy**: Only high-quality (75%+) faces enrolled
✅ **Better UX**: Users guided through enrollment with specific feedback

**Result**: More accurate, reliable, and auditable face attendance system.
