"""
ui/components/delete_dialog.py
Reusable confirmation dialog for safe deletion of medications and care recipients.
"""
import flet as ft
from database import delete_medication, delete_care_recipient

def show_delete_medication_dialog(page: ft.Page, med_id: int, med_name: str, on_deleted=None):
    """
    Displays an alert dialog asking for confirmation before deleting a medication.
    """
    def confirm_delete(e):
        delete_medication(med_id)
        page.pop_dialog()
        if on_deleted:
            on_deleted()
        page.update()

    def cancel_delete(e):
        page.pop_dialog()
        page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_600, size=22),
                ft.Text(f"Delete {med_name}?", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Text(
            f"Are you sure you want to delete '{med_name}'?\nThis will remove it from your active medication schedule and reminders.",
            size=13,
            color=ft.Colors.GREY_700,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=cancel_delete),
            ft.Button(
                "Delete",
                bgcolor=ft.Colors.RED_600,
                color=ft.Colors.WHITE,
                on_click=confirm_delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
    page.update()

def show_delete_recipient_dialog(page: ft.Page, recipient_id: int, recipient_name: str, on_deleted=None):
    """
    Displays an alert dialog asking for confirmation before deleting a care recipient.
    """
    def confirm_delete(e):
        delete_care_recipient(recipient_id)
        page.pop_dialog()
        if on_deleted:
            on_deleted()
        page.update()

    def cancel_delete(e):
        page.pop_dialog()
        page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_600, size=22),
                ft.Text(f"Remove {recipient_name}?", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Text(
            f"Are you sure you want to remove '{recipient_name}' from your care recipients?",
            size=13,
            color=ft.Colors.GREY_700,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=cancel_delete),
            ft.Button(
                "Remove",
                bgcolor=ft.Colors.RED_600,
                color=ft.Colors.WHITE,
                on_click=confirm_delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
    page.update()
