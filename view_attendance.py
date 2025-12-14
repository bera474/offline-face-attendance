#!/usr/bin/env python3
"""
Attendance Viewer Script
Displays attendance records in multiple formats:
1. Excel file (.xlsx)
2. CSV file (.csv)
3. Terminal table (beautiful ASCII format)
"""

import sqlite3
import csv
from datetime import datetime, timedelta
from pathlib import Path
import sys

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    print("[INFO] openpyxl not installed. Excel export will use CSV fallback.")
    print("       To enable Excel: pip install openpyxl\n")


def get_db_path():
    """Get database path from same directory as script or env variable"""
    script_dir = Path(__file__).parent
    db_path = script_dir / "attendance.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        sys.exit(1)
    
    return str(db_path)


def get_attendance_data(db_path, date=None, student_name=None):
    """
    Fetch attendance data from database
    
    Args:
        db_path: Path to attendance.db
        date: Specific date (YYYY-MM-DD) or None for today
        student_name: Filter by student name or None for all
    
    Returns:
        List of tuples: (name, timestamp, confidence, roll, class)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    if student_name:
        cursor.execute('''
            SELECT s.name, a.ts, ROUND(a.confidence, 3) as confidence, 
                   s.roll, s.class
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE DATE(a.ts) = ? AND s.name LIKE ?
            ORDER BY a.ts DESC
        ''', (date, f'%{student_name}%'))
    else:
        cursor.execute('''
            SELECT s.name, a.ts, ROUND(a.confidence, 3) as confidence,
                   s.roll, s.class
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE DATE(a.ts) = ?
            ORDER BY a.ts DESC
        ''', (date,))
    
    data = cursor.fetchall()
    conn.close()
    
    return data


def get_summary_data(db_path, date=None):
    """Get attendance summary (unique students per day)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # Get unique students marked today
    cursor.execute('''
        SELECT s.id, s.name, s.roll, s.class,
               COUNT(a.id) as marks, 
               ROUND(AVG(a.confidence), 3) as avg_confidence
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id 
                              AND DATE(a.ts) = ?
        GROUP BY s.id
        ORDER BY s.name
    ''', (date,))
    
    data = cursor.fetchall()
    conn.close()
    
    return data


def create_excel_file(db_path, output_file="attendance_report.xlsx", date=None):
    """Create Excel file with attendance data"""
    if not EXCEL_AVAILABLE:
        print("⚠️  openpyxl not installed. Use create_csv_file() instead.")
        return False
    
    data = get_attendance_data(db_path, date)
    summary = get_summary_data(db_path, date)
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # Create workbook
    wb = Workbook()
    
    # Remove default sheet and create new ones
    wb.remove(wb.active)
    
    # ===== SHEET 1: Detailed Attendance =====
    ws1 = wb.create_sheet("Detailed Attendance", 0)
    
    # Header
    ws1['A1'] = f"Detailed Attendance - {date}"
    ws1['A1'].font = Font(bold=True, size=14)
    ws1.merge_cells('A1:E1')
    
    # Column headers
    headers = ['Student Name', 'Roll No', 'Class', 'Time', 'Confidence']
    for col, header in enumerate(headers, 1):
        cell = ws1.cell(row=3, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Data rows
    for row_idx, (name, ts, confidence, roll, class_name) in enumerate(data, 4):
        ws1.cell(row=row_idx, column=1).value = name
        ws1.cell(row=row_idx, column=2).value = roll if roll else "-"
        ws1.cell(row=row_idx, column=3).value = class_name if class_name else "-"
        ws1.cell(row=row_idx, column=4).value = ts
        ws1.cell(row=row_idx, column=5).value = confidence
        
        # Center align confidence
        ws1.cell(row=row_idx, column=5).alignment = Alignment(horizontal="center")
        
        # Alternating row colors
        if row_idx % 2 == 0:
            for col in range(1, 6):
                ws1.cell(row=row_idx, column=col).fill = PatternFill(
                    start_color="E7E6E6", end_color="E7E6E6", fill_type="solid"
                )
    
    # Adjust column widths
    ws1.column_dimensions['A'].width = 25
    ws1.column_dimensions['B'].width = 15
    ws1.column_dimensions['C'].width = 15
    ws1.column_dimensions['D'].width = 30
    ws1.column_dimensions['E'].width = 12
    
    # Statistics row
    if data:
        stats_row = len(data) + 5
        ws1[f'A{stats_row}'] = "Total Records:"
        ws1[f'B{stats_row}'] = len(data)
        ws1[f'A{stats_row}'].font = Font(bold=True)
    
    # ===== SHEET 2: Daily Summary =====
    ws2 = wb.create_sheet("Daily Summary", 1)
    
    # Header
    ws2['A1'] = f"Daily Summary - {date}"
    ws2['A1'].font = Font(bold=True, size=14)
    ws2.merge_cells('A1:F1')
    
    # Column headers
    headers2 = ['Student Name', 'Roll No', 'Class', 'Status', 'Marks', 'Avg Confidence']
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=3, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Summary data
    for row_idx, (sid, name, roll, class_name, marks, avg_conf) in enumerate(summary, 4):
        ws2.cell(row=row_idx, column=1).value = name
        ws2.cell(row=row_idx, column=2).value = roll if roll else "-"
        ws2.cell(row=row_idx, column=3).value = class_name if class_name else "-"
        
        # Status (Present/Absent)
        status = "✓ Present" if marks and marks > 0 else "✗ Absent"
        ws2.cell(row=row_idx, column=4).value = status
        
        ws2.cell(row=row_idx, column=5).value = marks if marks else 0
        ws2.cell(row=row_idx, column=6).value = avg_conf if avg_conf else 0
        
        # Center alignment
        for col in [4, 5, 6]:
            ws2.cell(row=row_idx, column=col).alignment = Alignment(horizontal="center")
        
        # Color present/absent
        status_cell = ws2.cell(row=row_idx, column=4)
        if marks and marks > 0:
            status_cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        else:
            status_cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        
        # Alternating row colors
        if row_idx % 2 == 0:
            for col in range(1, 7):
                if col != 4:  # Don't override status color
                    ws2.cell(row=row_idx, column=col).fill = PatternFill(
                        start_color="E7E6E6", end_color="E7E6E6", fill_type="solid"
                    )
    
    # Adjust column widths
    ws2.column_dimensions['A'].width = 25
    ws2.column_dimensions['B'].width = 15
    ws2.column_dimensions['C'].width = 15
    ws2.column_dimensions['D'].width = 15
    ws2.column_dimensions['E'].width = 12
    ws2.column_dimensions['F'].width = 15
    
    # Statistics
    total_students = len(summary)
    present = sum(1 for _, _, _, _, marks, _ in summary if marks and marks > 0)
    absent = total_students - present
    
    stats_row = len(summary) + 5
    ws2[f'A{stats_row}'] = "Summary:"
    ws2[f'A{stats_row}'].font = Font(bold=True)
    
    ws2[f'A{stats_row + 1}'] = "Total Students:"
    ws2[f'B{stats_row + 1}'] = total_students
    
    ws2[f'A{stats_row + 2}'] = "Present:"
    ws2[f'B{stats_row + 2}'] = present
    ws2[f'B{stats_row + 2}'].fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    
    ws2[f'A{stats_row + 3}'] = "Absent:"
    ws2[f'B{stats_row + 3}'] = absent
    ws2[f'B{stats_row + 3}'].fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    
    # Save file
    wb.save(output_file)
    return True


def create_csv_file(db_path, output_file="attendance_report.csv", date=None):
    """Create CSV file with attendance data"""
    data = get_attendance_data(db_path, date)
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Attendance Report', date])
        writer.writerow([])
        writer.writerow(['Student Name', 'Roll No', 'Class', 'Time', 'Confidence'])
        
        for name, ts, confidence, roll, class_name in data:
            writer.writerow([
                name,
                roll if roll else '-',
                class_name if class_name else '-',
                ts,
                confidence
            ])
        
        writer.writerow([])
        writer.writerow(['Total Records:', len(data)])
    
    return True


def print_table(db_path, date=None):
    """Print attendance as ASCII table in terminal"""
    data = get_attendance_data(db_path, date)
    summary = get_summary_data(db_path, date)
    
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    print("\n" + "=" * 100)
    print(f"DETAILED ATTENDANCE REPORT - {date}".center(100))
    print("=" * 100)
    
    if data:
        print(f"\n{'Student Name':<25} {'Roll':<15} {'Class':<15} {'Time':<30} {'Confidence':<10}")
        print("-" * 100)
        
        for name, ts, confidence, roll, class_name in data:
            print(f"{name:<25} {str(roll):<15} {str(class_name):<15} {str(ts):<30} {str(confidence):<10}")
        
        print(f"\nTotal Records: {len(data)}")
    else:
        print("\n❌ No attendance records found for this date.\n")
    
    # Summary section
    print("\n" + "=" * 100)
    print(f"DAILY SUMMARY - {date}".center(100))
    print("=" * 100)
    
    if summary:
        print(f"\n{'Student Name':<25} {'Roll':<15} {'Class':<15} {'Status':<15} {'Marks':<10} {'Avg Confidence':<10}")
        print("-" * 100)
        
        present = 0
        for sid, name, roll, class_name, marks, avg_conf in summary:
            status = "✓ Present" if marks and marks > 0 else "✗ Absent"
            if marks and marks > 0:
                present += 1
            
            print(f"{name:<25} {str(roll):<15} {str(class_name):<15} {status:<15} {str(marks):<10} {str(avg_conf):<10}")
        
        total = len(summary)
        absent = total - present
        
        print("\n" + "-" * 100)
        print(f"Total Students: {total} | Present: {present} | Absent: {absent}")
        print("=" * 100 + "\n")
    else:
        print("\n❌ No students found in database.\n")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="View attendance records in multiple formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_attendance.py                    # Show today's attendance in terminal
  python view_attendance.py --excel            # Create Excel file for today
  python view_attendance.py --csv              # Create CSV file for today
  python view_attendance.py --all              # Create Excel + CSV + print
  python view_attendance.py --date 2025-12-13 # View specific date
  python view_attendance.py --name "John"      # Filter by student name
        """
    )
    
    parser.add_argument('--excel', action='store_true', help='Create Excel file')
    parser.add_argument('--csv', action='store_true', help='Create CSV file')
    parser.add_argument('--all', action='store_true', help='Create both Excel and CSV')
    parser.add_argument('--date', help='Date in format YYYY-MM-DD (default: today)')
    parser.add_argument('--name', help='Filter by student name')
    parser.add_argument('--output', help='Output filename (without extension)')
    
    args = parser.parse_args()
    
    # Set default output name
    output_name = args.output or "attendance_report"
    
    db_path = get_db_path()
    
    # Validate date format
    if args.date:
        try:
            datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print("❌ Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Default behavior: print table
    if not args.excel and not args.csv and not args.all:
        print_table(db_path, args.date)
        return
    
    # Create files
    if args.excel or args.all:
        if EXCEL_AVAILABLE:
            excel_file = f"{output_name}.xlsx"
            if create_excel_file(db_path, excel_file, args.date):
                print(f"✅ Excel file created: {excel_file}")
        else:
            print("⚠️  openpyxl not installed. Skipping Excel. Install with: pip install openpyxl")
    
    if args.csv or args.all:
        csv_file = f"{output_name}.csv"
        if create_csv_file(db_path, csv_file, args.date):
            print(f"✅ CSV file created: {csv_file}")
    
    # Also print table
    print_table(db_path, args.date)


if __name__ == "__main__":
    main()
