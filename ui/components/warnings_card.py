"""
ui/components/warnings_card.py
Component for rendering inventory stock and expiration date warnings.
"""
from datetime import date
from typing import List, Optional
import flet as ft

def build_warnings_card(
    meds: List[tuple],
    low_stock_threshold: int = 5,
    expiry_warning_days: int = 30
) -> Optional[ft.Container]:
    """
    Evaluates medication list for low stock and upcoming or past expiration dates.
    Returns a styled Container if warnings exist, otherwise None.
    """
    today = date.today()
    warning_lines = []

    for med in meds:
        name = med[2]
        quantity = med[9]
        expiry_str = med[10]

        if quantity is not None and quantity <= low_stock_threshold:
            warning_lines.append(f"{name}: only {quantity} left")

        if expiry_str:
            try:
                expiry = date.fromisoformat(expiry_str)
                days_left = (expiry - today).days
                if days_left < 0:
                    warning_lines.append(f"{name}: expired on {expiry_str}")
                elif days_left <= expiry_warning_days:
                    warning_lines.append(f"{name}: expires in {days_left} days ({expiry_str})")
            except ValueError:
                pass

    if not warning_lines:
        return None

    header = ft.Row(
        [
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.ORANGE_800, size=16),
            ft.Text(
                f"{len(warning_lines)} warning{'s' if len(warning_lines) != 1 else ''}",
                size=13,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.ORANGE_800
            ),
        ],
        spacing=6,
    )

    lines = [ft.Text(line, size=13, color=ft.Colors.ORANGE_800) for line in warning_lines]

    return ft.Container(
        content=ft.Column([header] + lines, spacing=4),
        bgcolor=ft.Colors.ORANGE_50,
        border_radius=12,
        padding=14,
    )
