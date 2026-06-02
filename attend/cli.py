"""
Command-line interface for offline attendance system.
"""
import sys
import argparse
from .enroll import enroll_from_webcam, enroll_from_dataset, update_student_image, delete_student
from .packs import download_models
from .db import init_db


def main():
    parser = argparse.ArgumentParser(description="Offline Face Attendance System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Init database
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument("--school-id", default="", help="School ID")
    init_parser.add_argument("--room", default="", help="Room name")

    # Enroll from webcam
    enroll_cam_parser = subparsers.add_parser("enroll", help="Enroll student via webcam")
    enroll_cam_parser.add_argument("--name", default=None, help="Student name")
    enroll_cam_parser.add_argument("--id", default=None, help="Student ID")
    enroll_cam_parser.add_argument("--shots", type=int, default=8, help="Number of face captures")
    enroll_cam_parser.add_argument("--device", type=int, default=0, help="Camera device index")

    # Enroll from dataset
    enroll_dataset_parser = subparsers.add_parser("enroll-dataset", help="Enroll from dataset directory")
    enroll_dataset_parser.add_argument("dataset_dir", help="Dataset directory path")

    # Download models
    models_parser = subparsers.add_parser("download-models", help="Pre-download models")
    models_parser.add_argument("--model", default=None, help="Model name")
    models_parser.add_argument("--antispoof", action="store_true", help="Download anti-spoof model")

    # Run attendance
    run_parser = subparsers.add_parser("run", help="Run attendance marking")
    run_parser.add_argument("--device", type=int, default=0, help="Camera device index")

    # Update student image
    update_parser = subparsers.add_parser("update", help="Update student's face image")
    update_parser.add_argument("--name", required=True, help="Student name")
    update_parser.add_argument("--shots", type=int, default=8, help="Number of face captures")
    update_parser.add_argument("--device", type=int, default=0, help="Camera device index")

    # Delete student
    delete_parser = subparsers.add_parser("delete", help="Delete a student")
    delete_parser.add_argument("--name", required=True, help="Student name to delete")

    # Delete attendance for a date
    del_att_parser = subparsers.add_parser("delete-attendance", help="Delete attendance records for a date")
    del_att_parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format (default: today)")
    del_att_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "init":
        init_db(school_id=args.school_id, room=args.room)
    elif args.command == "enroll":
        enroll_from_webcam(
            student_id=args.id,
            name=args.name,
            device=args.device,
            n_shots=args.shots,
        )
    elif args.command == "enroll-dataset":
        enroll_from_dataset(args.dataset_dir)
    elif args.command == "download-models":
        download_models(model_name=args.model)
        if args.antispoof:
            from .packs import download_antispoof_models
            download_antispoof_models()
    elif args.command == "run":
        from .app import run_attendance
        run_attendance(camera_index=args.device)
    elif args.command == "update":
        update_student_image(
            name=args.name,
            device=args.device,
            n_shots=args.shots,
        )
    elif args.command == "delete":
        delete_student(name=args.name)
    elif args.command == "delete-attendance":
        from datetime import datetime
        from .attendance import delete_attendance_by_date
        date = args.date or datetime.now().strftime("%Y-%m-%d")
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
        # Confirmation
        if not args.yes:
            confirm = input(f"⚠️  Delete ALL attendance records for {date}? (y/N): ")
            if confirm.lower() not in ("y", "yes"):
                print("Cancelled.")
                return
        deleted = delete_attendance_by_date(date)
        print(f"✅ Deleted {deleted} attendance record(s) for {date}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
