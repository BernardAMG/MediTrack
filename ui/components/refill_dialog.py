"""
MediTrack Quick Refill Modal Dialog
"""

import flet as ft
from database import refill_medication

def show_refill_dialog(page: ft.Page, med_id: int, med_name: str, current_qty: int, on_refill_success=None):
    """
    Displays the refill modal dialog allowing quick stock increment.
    """
    refill_qty_field = ft.TextField(
        label="Quantity to add",
        value="30",
        keyboard_type=ft.KeyboardType.NUMBER,
        width=140,
        autofocus=True,
    )
    error_msg = ft.Text(value="", size=12, color=ft.Colors.RED_500)

    def confirm_refill(e):
        val = refill_qty_field.value.strip()
        if not val.isdigit() or int(val) <= 0:
            error_msg.value = "Enter a valid positive number"
            page.update()
            return

        refill_medication(med_id, int(val))
        page.pop_dialog()
        if on_refill_success:
            on_refill_success()
        page.update()

    def cancel_refill(e):
        page.pop_dialog()
        page.update()

    # Enable Enter key submit in the refill quantity input
    refill_qty_field.on_submit = confirm_refill

    curr_text = f"{current_qty} pills remaining" if current_qty is not None else "Stock not tracked"
    dlg = ft.AlertDialog(
        title=ft.Text(f"Refill {med_name}"),
        content=ft.Column(
            [
                ft.Text(f"Current stock: {curr_text}"),
                refill_qty_field,
                error_msg,
            ],
            tight=True,
            spacing=8
        ),
        actions=[
            ft.TextButton("Cancel", on_click=cancel_refill),
            ft.Button("Refill", on_click=confirm_refill),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
    page.update()
