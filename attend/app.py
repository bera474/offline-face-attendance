"""
Main application module for offline face attendance system.
Handles real-time face recognition and attendance marking.
"""
import cv2
import numpy as np
from collections import deque
from time import time
from datetime import datetime

from .db import connect, init_db, get_device_id
from .embeddings import Embedder
from .recognition import best_match
from .attendance import mark_attendance, get_student_count_today
from .camera import Camera
from .config import CFG
from .utils import now_utc_iso


class AttendanceSystem:
    def __init__(self, camera_index: int = 0):
        """Initialize attendance system with embedder and camera."""
        self.camera_index = camera_index
        self.embedder = Embedder()
        self.camera = Camera(camera_index)
        self.conn = None
        self.device_id = None

        # Load enrolled students
        self.enrolled_students = self._load_enrolled()

        # Rearm timer: prevent same student from being marked multiple times
        self.last_marked_time = {}

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

        try:
            while True:
                ok, frame = self.camera.read()
                if not ok:
                    break

                # Detect faces
                faces = self.embedder.detect_and_embed(frame)

                # Display frame with results
                disp = frame.copy()

                for face in faces:
                    bbox = face["bbox"]
                    embedding = face["embedding"]

                    # Proceed with matching
                    query_list = [(sid, name, vec) for sid, name, vec in self.enrolled_students]
                    if query_list:
                        best_id_tuple = best_match(embedding, query_list)
                        best_id, best_sim = best_id_tuple if best_id_tuple[0] else (None, 0.0)

                        if best_id and best_sim >= CFG.SIM_THRESHOLD:
                            # Match found
                            name = self._get_name_from_id(best_id)
                            color = (0, 255, 0)  # Green

                            if self._can_mark(best_id):
                                mark_attendance(best_id, self.device_id, method="face", confidence=best_sim)
                                if CFG.LOG_MATCHES:
                                    print(f"[marked] {name} ({best_id}) @ {now_utc_iso()} (conf: {best_sim:.3f})")
                        else:
                            # No match
                            name = "Unknown"
                            color = (0, 0, 255)  # Red
                            best_sim = 0.0

                        # Draw bounding box
                        x1, y1, x2, y2 = bbox
                        cv2.rectangle(disp, (x1, y1), (x2, y2), color, 2)

                        # Draw label
                        label = f"{name}"
                        if CFG.SHOW_CONFIDENCE:
                            label += f" ({best_sim:.2f})"
                        cv2.putText(
                            disp,
                            label,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            color,
                            2,
                        )

                # Add statistics
                count_today = get_student_count_today(self.device_id)
                cv2.putText(
                    disp,
                    f"Present Today: {count_today}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )

                # Show frame
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
