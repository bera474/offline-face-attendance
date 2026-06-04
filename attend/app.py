"""
Main application module for offline face attendance system.
Handles real-time face recognition and attendance marking.
"""
import cv2
import numpy as np
import random
from collections import deque
from time import time
from datetime import datetime

from .db import connect, init_db, get_device_id
from .embeddings import Embedder
from .recognition import best_match
from .attendance import mark_attendance, get_student_count_today
from .camera import Camera
from .config import CFG
from .liveness import LivenessChecker
from .utils import now_utc_iso, cosine_sim
from .quality import estimate_face_angle


class AttendanceSystem:
    def __init__(self, camera_index: int = 0):
        """Initialize attendance system with embedder and camera."""
        self.camera_index = camera_index
        self.embedder = Embedder()
        self.camera = Camera(camera_index)
        self.liveness_checker = LivenessChecker()
        self.conn = None
        self.device_id = None

        # Load enrolled students
        self.enrolled_students = self._load_enrolled()

        # Rearm timer: prevent same student from being marked multiple times
        self.last_marked_time = {}

        # Active Liveness State Machine
        self.challenge_state = "IDLE"  # "IDLE", "PROMPTED", "ACTION_DONE"
        self.challenge_user_id = None
        self.challenge_user_name = None
        self.challenge_direction = None  # "left" or "right"
        self.challenge_start_time = 0.0
        self.challenge_face_lost_time = 0.0
        self.challenge_timeout_show_until = 0.0
        
        # Blink Tracking State
        self.challenge_blink_stage = 0  # 0: open, 1: closed, 2: open again (passed)
        self.challenge_blink_open_frames = 0
        self.challenge_ear_history = deque(maxlen=10)

    def _load_enrolled(self) -> list:
        """Load enrolled students and their embeddings from database."""
        conn = connect()
        rows = conn.execute(
            """
            SELECT s.id, s.name, e.vec FROM students s
            JOIN embeddings e ON s.id = e.student_id
            WHERE s.status = 'active' AND s.deleted = 0
            """
        ).fetchall()
        conn.close()

        enrolled = []
        for student_id, name, vec_bytes in rows:
            vec = np.frombuffer(vec_bytes, dtype=np.float32)
            enrolled.append((student_id, name, vec))

        if CFG.LOG_MATCHES:
            print(f"[system] Loaded {len(enrolled)} enrolled students")
        return enrolled

    def _get_name_from_id(self, student_id: str) -> str:
        """Get student name from ID."""
        for sid, name, _ in self.enrolled_students:
            if sid == student_id:
                return name
        return "Unknown"

    def _can_mark(self, student_id: str) -> bool:
        """Check if student can be marked (rearm timeout)."""
        now = time()
        last_time = self.last_marked_time.get(student_id, 0)
        if now - last_time >= CFG.REARM_SECONDS:
            self.last_marked_time[student_id] = now
            return True
        return False

    def run(self):
        """Main loop for attendance marking."""
        if not self.camera.open():
            print("[system] Cannot open camera")
            return

        self.conn = connect()
        self.device_id = get_device_id(self.conn)

        print(f"[system] Device ID: {self.device_id}")
        print(f"[system] Running attendance system. Press 'q' to quit.")
        print(f"[system] Threshold: {CFG.SIM_THRESHOLD}, Rearm: {CFG.REARM_SECONDS}s")
        if CFG.LIVENESS_ENABLED:
            print(f"[system] Passive liveness: ON (threshold: {CFG.LIVENESS_THRESHOLD})")
        else:
            print(f"[system] Passive liveness: OFF")

        if CFG.ACTIVE_LIVENESS_ENABLED:
            print(f"[system] Active liveness: ON (timeout: {CFG.ACTIVE_LIVENESS_TIMEOUT}s, yaw threshold: {CFG.ACTIVE_LIVENESS_YAW_THRESHOLD})")
        else:
            print(f"[system] Active liveness: OFF")

        try:
            while True:
                ok, frame = self.camera.read()
                if not ok:
                    break

                # 1. Handle Active Liveness Timeout if challenge is active
                if CFG.ACTIVE_LIVENESS_ENABLED and self.challenge_state != "IDLE":
                    if time() - self.challenge_start_time > CFG.ACTIVE_LIVENESS_TIMEOUT:
                        if CFG.LOG_LIVENESS:
                            print(f"[active-liveness] Challenge TIMEOUT for {self.challenge_user_name}")
                        self.challenge_state = "IDLE"
                        self.challenge_user_id = None
                        self.challenge_user_name = None
                        self.challenge_direction = None
                        self.challenge_blink_stage = 0
                        self.challenge_blink_open_frames = 0
                        self.challenge_ear_history.clear()
                        self.challenge_timeout_show_until = time() + 1.5

                # 2. Detect faces in frame
                faces = self.embedder.detect_and_embed(frame)

                # 3. Locate active user face if challenge is ongoing
                active_face = None
                active_face_sim = 0.0
                if CFG.ACTIVE_LIVENESS_ENABLED and self.challenge_state != "IDLE":
                    active_ref_vec = None
                    for sid, name, vec in self.enrolled_students:
                        if sid == self.challenge_user_id:
                            active_ref_vec = vec
                            break
                    if active_ref_vec is not None:
                        best_sim = -1.0
                        for face in faces:
                            sim = cosine_sim(face["embedding"], active_ref_vec)
                            if sim >= CFG.SIM_THRESHOLD and sim > best_sim:
                                best_sim = sim
                                active_face = face
                                active_face_sim = sim

                # 4. Process ongoing Active Liveness Challenge state machine
                liveness_score = 0.5
                if CFG.ACTIVE_LIVENESS_ENABLED and self.challenge_state != "IDLE":
                    if active_face is not None:
                        self.challenge_face_lost_time = 0.0
                        
                        # Verify passive liveness first on active challenge face
                        passive_ok = True
                        if CFG.LIVENESS_ENABLED:
                            liveness_result = self.liveness_checker.check(frame, active_face["bbox"])
                            liveness_score = liveness_result["score"]
                            if not liveness_result["is_live"]:
                                passive_ok = False
                        
                        if not passive_ok:
                            if CFG.LOG_LIVENESS:
                                print(f"[active-liveness] Passive check failed during active challenge for {self.challenge_user_name}")
                            self.challenge_state = "IDLE"
                            self.challenge_user_id = None
                            self.challenge_user_name = None
                            self.challenge_direction = None
                            self.challenge_blink_stage = 0
                            self.challenge_blink_open_frames = 0
                            self.challenge_ear_history.clear()
                            self.challenge_timeout_show_until = time() + 1.5
                        else:
                            # Estimate yaw with sign to find turn direction
                            left_eye = active_face["kps"][0]
                            right_eye = active_face["kps"][1]
                            nose = active_face["kps"][2]
                            eye_center = (left_eye + right_eye) / 2.0
                            yaw_offset = nose[0] - eye_center[0]
                            eye_distance = np.abs(right_eye[0] - left_eye[0])
                            
                            signed_yaw = 0.0
                            if eye_distance > 0:
                                signed_yaw = float((yaw_offset / eye_distance) * 180.0 / np.pi)
                                
                            # Print debug info to console for active tuning
                            if CFG.LOG_LIVENESS:
                                print(f"[active-liveness-debug] name: {self.challenge_user_name}, target: {self.challenge_direction}, yaw: {signed_yaw:.1f}, threshold: {CFG.ACTIVE_LIVENESS_YAW_THRESHOLD:.1f}")

                            # Check challenge criteria
                            if self.challenge_state == "PROMPTED":
                                if self.challenge_direction == "left" and signed_yaw > CFG.ACTIVE_LIVENESS_YAW_THRESHOLD:
                                    self.challenge_state = "ACTION_DONE"
                                    self.challenge_start_time = time()
                                    self.challenge_ear_history.clear()
                                    if CFG.LOG_LIVENESS:
                                        print(f"[active-liveness] {self.challenge_user_name} turned left successfully (yaw: {signed_yaw:.1f})")
                                elif self.challenge_direction == "right" and signed_yaw < -CFG.ACTIVE_LIVENESS_YAW_THRESHOLD:
                                    self.challenge_state = "ACTION_DONE"
                                    self.challenge_start_time = time()
                                    self.challenge_ear_history.clear()
                                    if CFG.LOG_LIVENESS:
                                        print(f"[active-liveness] {self.challenge_user_name} turned right successfully (yaw: {signed_yaw:.1f})")
                            elif self.challenge_state == "ACTION_DONE":
                                is_straight = np.abs(signed_yaw) < 8.0
                                blink_passed = False
                                
                                if is_straight:
                                    # Calculate average EAR from 3D landmarks
                                    lmk = active_face.get("landmark_3d_68", None)
                                    ear_avg = 0.30
                                    if lmk is not None and len(lmk) >= 68:
                                        le = lmk[36:42]
                                        re = lmk[42:48]
                                        
                                        # Left eye EAR
                                        dl1 = np.linalg.norm(le[1] - le[5])
                                        dl2 = np.linalg.norm(le[2] - le[4])
                                        dl3 = np.linalg.norm(le[0] - le[3])
                                        ear_l = (dl1 + dl2) / (2.0 * dl3 + 1e-6)
                                        
                                        # Right eye EAR
                                        dr1 = np.linalg.norm(re[1] - re[5])
                                        dr2 = np.linalg.norm(re[2] - re[4])
                                        dr3 = np.linalg.norm(re[0] - re[3])
                                        ear_r = (dr1 + dr2) / (2.0 * dr3 + 1e-6)
                                        
                                        ear_avg = float((ear_l + ear_r) / 2.0)
                                        
                                    self.challenge_ear_history.append(ear_avg)
                                    
                                    # Sliding window blink detection:
                                    if len(self.challenge_ear_history) >= 5:
                                        max_ear = max(self.challenge_ear_history)
                                        min_ear = min(self.challenge_ear_history)
                                        diff = max_ear - min_ear
                                        
                                        # Blink criteria:
                                        # 1. Significant EAR drop (diff >= 0.025)
                                        # 2. Eye has reopened (current ear_avg >= max_ear - 0.02)
                                        # 3. Eye has reopened from minimum (current ear_avg >= min_ear + 0.015)
                                        if diff >= 0.025 and ear_avg >= max_ear - 0.02 and ear_avg >= min_ear + 0.015:
                                            blink_passed = True
                                            if CFG.LOG_LIVENESS:
                                                print(f"[active-liveness] Window blink detected (ear: {ear_avg:.3f}, min: {min_ear:.3f}, max: {max_ear:.3f}, diff: {diff:.3f})")
                                                
                                    if CFG.LOG_LIVENESS:
                                        print(f"[active-liveness-debug] name: {self.challenge_user_name}, state: {self.challenge_state}, ear: {ear_avg:.3f}, history_len: {len(self.challenge_ear_history)}")
                                
                                if is_straight and blink_passed:
                                    # Challenge passed! Mark attendance
                                    mark_attendance(
                                        self.challenge_user_id,
                                        self.device_id,
                                        method="face-active",
                                        confidence=active_face_sim,
                                        liveness_score=liveness_score,
                                    )
                                    self.last_marked_time[self.challenge_user_id] = time()
                                    if CFG.LOG_MATCHES:
                                        print(
                                            f"[marked-active] {self.challenge_user_name} ({self.challenge_user_id}) @ {now_utc_iso()} "
                                            f"(conf: {active_face_sim:.3f}, live: {liveness_score:.2f}, active: passed)"
                                        )
                                    # Reset challenge
                                    self.challenge_state = "IDLE"
                                    self.challenge_user_id = None
                                    self.challenge_user_name = None
                                    self.challenge_direction = None
                                    self.challenge_blink_stage = 0
                                    self.challenge_blink_open_frames = 0
                                    self.challenge_ear_history.clear()
                    else:
                        # Face lost tracker
                        if self.challenge_face_lost_time == 0.0:
                            self.challenge_face_lost_time = time()
                        elif time() - self.challenge_face_lost_time > 1.5:
                            if CFG.LOG_LIVENESS:
                                print(f"[active-liveness] Challenge CANCELLED: Face lost for {self.challenge_user_name}")
                            self.challenge_state = "IDLE"
                            self.challenge_user_id = None
                            self.challenge_user_name = None
                            self.challenge_direction = None
                            self.challenge_blink_stage = 0
                            self.challenge_blink_open_frames = 0
                            self.challenge_ear_history.clear()

                # 5. Prepare output frame
                disp = frame.copy()

                # Draw overlay and stats
                if CFG.ACTIVE_LIVENESS_ENABLED and self.challenge_state != "IDLE":
                    # Rendering loop when active challenge is ongoing
                    for face in faces:
                        bbox = face["bbox"]
                        x1, y1, x2, y2 = bbox
                        
                        if face is active_face:
                            # Draw active challenge details
                            if self.challenge_state == "PROMPTED":
                                color = (0, 165, 255)  # Orange/Yellow
                                label = f"{self.challenge_user_name}: TURN {self.challenge_direction.upper()}"
                                arrow_x = (x1 + x2) // 2
                                arrow_y = y1 - 30
                                if self.challenge_direction == "left":
                                    cv2.putText(disp, "<- <- <-", (arrow_x - 50, arrow_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                                else:
                                    cv2.putText(disp, "-> -> ->", (arrow_x - 50, arrow_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                            else:  # ACTION_DONE
                                color = (255, 255, 0)  # Cyan
                                label = f"{self.challenge_user_name}: LOOK STRAIGHT & BLINK"
                            
                            cv2.rectangle(disp, (x1, y1), (x2, y2), color, 3)
                            cv2.putText(disp, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        else:
                            # Inactive face during challenge
                            cv2.rectangle(disp, (x1, y1), (x2, y2), (100, 100, 100), 1)
                            cv2.putText(disp, "Waiting...", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
                else:
                    # Rendering loop when IDLE (normal recognition)
                    for face in faces:
                        bbox = face["bbox"]
                        embedding = face["embedding"]
                        x1, y1, x2, y2 = bbox

                        query_list = [(sid, name, vec) for sid, name, vec in self.enrolled_students]
                        if query_list:
                            best_id_tuple = best_match(embedding, query_list)
                            best_id, best_sim = best_id_tuple if best_id_tuple[0] else (None, 0.0)

                            if best_id and best_sim >= CFG.SIM_THRESHOLD:
                                name = self._get_name_from_id(best_id)
                                is_rearmed = (time() - self.last_marked_time.get(best_id, 0)) >= CFG.REARM_SECONDS

                                if is_rearmed:
                                    # Trigger active liveness or mark directly
                                    if CFG.ACTIVE_LIVENESS_ENABLED:
                                        passive_ok = True
                                        if CFG.LIVENESS_ENABLED:
                                            liveness_result = self.liveness_checker.check(frame, bbox)
                                            liveness_score = liveness_result["score"]
                                            if not liveness_result["is_live"]:
                                                passive_ok = False
                                        
                                        if passive_ok:
                                            # Initiate active liveness challenge
                                            self.challenge_state = "PROMPTED"
                                            self.challenge_user_id = best_id
                                            self.challenge_user_name = name
                                            self.challenge_direction = random.choice(["left", "right"])
                                            self.challenge_start_time = time()
                                            self.challenge_face_lost_time = 0.0
                                            self.challenge_blink_stage = 0
                                            self.challenge_blink_open_frames = 0
                                            self.challenge_ear_history.clear()
                                            if CFG.LOG_LIVENESS:
                                                print(f"[active-liveness] Challenge STARTED for {name}: TURN {self.challenge_direction.upper()}")
                                            break  # Focus on the challenge user
                                        else:
                                            # Spoof rejected
                                            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                            cv2.putText(disp, f"SPOOF ({liveness_score:.2f})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                            if CFG.LOG_LIVENESS:
                                                print(f"[spoof] Face rejected (score: {liveness_score:.3f})")
                                    else:
                                        # Passive liveness only
                                        passive_ok = True
                                        if CFG.LIVENESS_ENABLED:
                                            liveness_result = self.liveness_checker.check(frame, bbox)
                                            liveness_score = liveness_result["score"]
                                            if not liveness_result["is_live"]:
                                                passive_ok = False
                                        
                                        if passive_ok:
                                            mark_attendance(
                                                best_id,
                                                self.device_id,
                                                method="face",
                                                confidence=best_sim,
                                                liveness_score=liveness_score,
                                            )
                                            self.last_marked_time[best_id] = time()
                                            if CFG.LOG_MATCHES:
                                                print(f"[marked] {name} ({best_id}) @ {now_utc_iso()} (conf: {best_sim:.3f}, live: {liveness_score:.2f})")
                                            
                                            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                            cv2.putText(disp, f"{name} ({best_sim:.2f})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                                        else:
                                            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                            cv2.putText(disp, f"SPOOF ({liveness_score:.2f})", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                            if CFG.LOG_LIVENESS:
                                                print(f"[spoof] Face rejected (score: {liveness_score:.3f})")
                                else:
                                    # Rearm active (marked recently)
                                    cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                    cv2.putText(disp, f"{name} (marked)", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                            else:
                                # Unknown face
                                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(disp, "Unknown", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # 6. Render Active Liveness Banner Overlays
                if CFG.ACTIVE_LIVENESS_ENABLED:
                    if self.challenge_state == "PROMPTED":
                        overlay = disp.copy()
                        cv2.rectangle(overlay, (0, 0), (disp.shape[1], 55), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.6, disp, 0.4, 0, disp)
                        
                        instruction = f"LIVENESS CHALLENGE: {self.challenge_user_name.upper()}, TURN {self.challenge_direction.upper()}"
                        cv2.putText(disp, instruction, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                        
                        # Progress bar
                        elapsed = time() - self.challenge_start_time
                        pct = max(0.0, 1.0 - (elapsed / CFG.ACTIVE_LIVENESS_TIMEOUT))
                        bar_w = int(disp.shape[1] * pct)
                        cv2.rectangle(disp, (0, 50), (bar_w, 55), (0, 165, 255), -1)
                    elif self.challenge_state == "ACTION_DONE":
                        overlay = disp.copy()
                        cv2.rectangle(overlay, (0, 0), (disp.shape[1], 55), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.6, disp, 0.4, 0, disp)
                        
                        instruction = f"GOOD! {self.challenge_user_name.upper()}, NOW LOOK STRAIGHT & BLINK"
                        cv2.putText(disp, instruction, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                        
                        # Progress bar for blink stage
                        elapsed = time() - self.challenge_start_time
                        pct = max(0.0, 1.0 - (elapsed / CFG.ACTIVE_LIVENESS_TIMEOUT))
                        bar_w = int(disp.shape[1] * pct)
                        cv2.rectangle(disp, (0, 50), (bar_w, 55), (255, 255, 0), -1)
                    elif time() < self.challenge_timeout_show_until:
                        overlay = disp.copy()
                        cv2.rectangle(overlay, (0, 0), (disp.shape[1], 55), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.6, disp, 0.4, 0, disp)
                        
                        cv2.putText(disp, "CHALLENGE FAILED / TIMEOUT", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Add statistics overlay
                count_today = get_student_count_today(self.device_id)
                cv2.putText(
                    disp,
                    f"Present Today: {count_today}",
                    (10, disp.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )

                # Show output frame
                cv2.imshow(CFG.WINDOW_NAME, disp)

                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.camera.release()
            if self.conn:
                self.conn.close()
            cv2.destroyAllWindows()
            print("[system] Attendance system stopped")


def run_attendance(camera_index: int = 0, school_id: str = "", room: str = ""):
    """
    Initialize and run the attendance system.
    """
    init_db(school_id=school_id, room=room)
    system = AttendanceSystem(camera_index=camera_index)
    system.run()


if __name__ == "__main__":
    run_attendance()
