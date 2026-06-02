import cv2
import numpy as np
from .config import CFG


def calculate_face_size(bbox, frame_shape) -> dict:
    """
    Calculate face size relative to frame.

    Args:
        bbox: (x1, y1, x2, y2) face bounding box
        frame_shape: (height, width, channels) frame shape

    Returns:
        {"score": float (0-1), "issue": str or None, "face_area_pct": float}
    """
    x1, y1, x2, y2 = bbox
    face_width = x2 - x1
    face_height = y2 - y1
    face_area = face_width * face_height

    frame_area = frame_shape[0] * frame_shape[1]
    size_ratio = face_area / frame_area if frame_area > 0 else 0

    if size_ratio < CFG.QUALITY_MIN_FACE_SIZE:
        return {"score": 0.0, "issue": "Face too small, move closer", "face_area_pct": size_ratio * 100}

    if size_ratio > 0.5:
        return {"score": 0.0, "issue": "Face too close, move back", "face_area_pct": size_ratio * 100}

    score = min(1.0, size_ratio / CFG.QUALITY_MIN_FACE_SIZE)
    return {"score": score, "issue": None, "face_area_pct": size_ratio * 100}


def estimate_face_angle(keypoints) -> dict:
    """
    Estimate face 3D angles (yaw, pitch, roll) from 5 facial keypoints.
    Uses simple heuristics based on keypoint positions.

    Args:
        keypoints: ndarray (5, 2) - 5 facial landmarks

    Returns:
        {"yaw": float, "pitch": float, "roll": float, "issues": []}
    """
    if keypoints is None or len(keypoints) < 5:
        return {"yaw": 0, "pitch": 0, "roll": 0, "issues": []}

    issues = []

    # Keypoints typically: [left_eye, right_eye, nose, left_mouth, right_mouth]
    left_eye = keypoints[0]
    right_eye = keypoints[1]
    nose = keypoints[2]

    eye_center = (left_eye + right_eye) / 2

    # YAW: Check if nose is centered between eyes
    yaw_offset = nose[0] - eye_center[0]
    yaw_pixels = np.abs(yaw_offset)
    eye_distance = np.abs(right_eye[0] - left_eye[0])

    if eye_distance > 0:
        yaw_ratio = yaw_pixels / eye_distance
        yaw = np.arctan(yaw_ratio) * 180 / np.pi
    else:
        yaw = 0

    # PITCH: Check if nose is vertically aligned with eyes
    pitch_offset = nose[1] - eye_center[1]
    pitch = np.arctan(pitch_offset / (eye_distance + 1e-6)) * 180 / np.pi

    # ROLL: Check if eyes are horizontally aligned
    eye_angle = np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0])
    roll = eye_angle * 180 / np.pi

    # Check thresholds
    if np.abs(yaw) > CFG.QUALITY_MAX_YAW:
        issues.append(f"Head rotated {np.abs(yaw):.0f}°, face camera")

    if np.abs(pitch) > CFG.QUALITY_MAX_PITCH:
        issues.append(f"Head tilted {np.abs(pitch):.0f}°, look straight ahead")

    if np.abs(roll) > CFG.QUALITY_MAX_ROLL:
        issues.append(f"Head rotated {np.abs(roll):.0f}°, straighten head")

    return {
        "yaw": float(yaw),
        "pitch": float(pitch),
        "roll": float(roll),
        "issues": issues
    }


def detect_blur(face_roi) -> dict:
    """
    Detect blur in face region using Laplacian variance.

    Args:
        face_roi: cropped face image (BGR)

    Returns:
        {"score": float (0-1), "issue": str or None, "variance": float}
    """
    if face_roi is None or face_roi.size == 0:
        return {"score": 0.0, "issue": "No face region", "variance": 0.0}

    try:
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if laplacian_var < CFG.QUALITY_MIN_BLUR_SCORE:
            return {
                "score": 0.0,
                "issue": "Image too blurry, hold still",
                "variance": float(laplacian_var)
            }

        score = min(1.0, laplacian_var / (CFG.QUALITY_MIN_BLUR_SCORE * 3))
        return {
            "score": score,
            "issue": None,
            "variance": float(laplacian_var)
        }
    except Exception as e:
        return {"score": 0.5, "issue": None, "variance": 0.0}


def estimate_lighting(face_roi) -> dict:
    """
    Estimate lighting quality by checking brightness range.

    Args:
        face_roi: cropped face image (BGR)

    Returns:
        {"score": float (0-1), "issue": str or None, "brightness": float}
    """
    if face_roi is None or face_roi.size == 0:
        return {"score": 0.0, "issue": "No face region", "brightness": 0.0}

    try:
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        if mean_brightness < CFG.QUALITY_MIN_BRIGHTNESS:
            return {
                "score": 0.0,
                "issue": "Too dark, improve lighting",
                "brightness": float(mean_brightness)
            }

        if mean_brightness > CFG.QUALITY_MAX_BRIGHTNESS:
            return {
                "score": 0.0,
                "issue": "Too bright, reduce lighting",
                "brightness": float(mean_brightness)
            }

        # Score high for middle brightness range
        ideal_brightness = (CFG.QUALITY_MIN_BRIGHTNESS + CFG.QUALITY_MAX_BRIGHTNESS) / 2
        brightness_range = CFG.QUALITY_MAX_BRIGHTNESS - CFG.QUALITY_MIN_BRIGHTNESS
        distance = np.abs(mean_brightness - ideal_brightness)
        score = 1.0 - (distance / (brightness_range / 2))
        score = max(0.5, min(1.0, score))

        return {
            "score": score,
            "issue": None,
            "brightness": float(mean_brightness)
        }
    except Exception:
        return {"score": 0.5, "issue": None, "brightness": 128.0}


def overall_quality_score(bbox, keypoints, frame) -> dict:
    """
    Calculate overall face quality score combining all checks.

    Args:
        bbox: (x1, y1, x2, y2) bounding box
        keypoints: ndarray (5, 2) facial landmarks
        frame: full BGR frame

    Returns:
        {
            "score": float (0-1),
            "percentage": int (0-100),
            "issues": [list of problems],
            "details": {
                "size": {...},
                "angle": {...},
                "blur": {...},
                "lighting": {...}
            }
        }
    """
    x1, y1, x2, y2 = bbox
    face_roi = frame[y1:y2, x1:x2]

    # Get individual scores
    size_result = calculate_face_size(bbox, frame.shape)
    angle_result = estimate_face_angle(keypoints)
    blur_result = detect_blur(face_roi)
    lighting_result = estimate_lighting(face_roi)

    # Collect all issues
    all_issues = []
    if size_result["issue"]:
        all_issues.append(size_result["issue"])
    all_issues.extend(angle_result["issues"])
    if blur_result["issue"]:
        all_issues.append(blur_result["issue"])
    if lighting_result["issue"]:
        all_issues.append(lighting_result["issue"])

    # Compute weighted average score
    # Reduced angle weight (0.1 instead of 0.25) since head tilt is less critical
    # for low-quality cameras in real classrooms
    scores = [
        size_result["score"] * 0.3,    # Face size (30%)
        (1.0 - min(1.0, np.linalg.norm([angle_result["yaw"]/CFG.QUALITY_MAX_YAW,
                                         angle_result["pitch"]/CFG.QUALITY_MAX_PITCH,
                                         angle_result["roll"]/CFG.QUALITY_MAX_ROLL]))) * 0.1,  # Angle (10%)
        blur_result["score"] * 0.3,    # Blur detection (30%)
        lighting_result["score"] * 0.3  # Lighting (30%)
    ]

    overall_score = np.mean(scores)
    overall_score = max(0.0, min(1.0, overall_score))

    return {
        "score": float(overall_score),
        "percentage": int(overall_score * 100),
        "issues": all_issues,
        "passed": overall_score >= CFG.QUALITY_ACCEPT_THRESHOLD,
        "details": {
            "size": size_result,
            "angle": angle_result,
            "blur": blur_result,
            "lighting": lighting_result
        }
    }
