"""
services/adherence.py
Domain service for calculating adherence statistics and formatting clinical reports.
"""
from typing import List, Tuple

def calculate_adherence_stats(dose_records: List[Tuple]) -> Tuple[int, int, int]:
    """
    Computes adherence percentage and counts from dose history records.
    Record schema expects status at index 1: (med_name, status, taken_at, sched_time).
    Returns:
        (percentage, taken_count, total_count)
    """
    total = len(dose_records)
    if total == 0:
        return 0, 0, 0

    taken_count = sum(1 for record in dose_records if len(record) > 1 and record[1] == "taken")
    percentage = round((taken_count / total) * 100)
    return percentage, taken_count, total

def format_adherence_summary(dose_records: List[Tuple]) -> str:
    """
    Formats adherence metrics into human-readable summary string for UI display.
    """
    percentage, taken_count, total = calculate_adherence_stats(dose_records)
    if total == 0:
        return "No doses logged yet."
    return f"{percentage}% adherence ({taken_count} of {total} doses taken)"
