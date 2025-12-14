"""
Offline Face Attendance System
"""

from .app import AttendanceSystem, run_attendance
from .enroll import enroll_from_webcam, enroll_from_dataset
from .cli import main

__all__ = [
    "AttendanceSystem",
    "run_attendance",
    "enroll_from_webcam",
    "enroll_from_dataset",
    "main",
]
