"""
ui/components/medication_drawer.py
Faithful implementation of the Page 2 Add/Edit Medication modal dialog.
Includes medication identity, form selector, schedule, supply, and reminder toggles.
"""
import flet as ft
from services.watcher import normalize_time
from database import (
    insert_medication,
    update_medication,
    get_care_recipients_for_caregiver
)

def show_medication_drawer(
    page: ft.Page,
    user_id: int,
    editing_med=None,
    on_saved=None
):
    """
    Opens the Add/Edit Medication modal dialog matching Page 2 of the reference design.
    """
    is_editing = editing_med is not None
    med_id = editing_med[0] if is_editing else None

    # Form fields
    name_field = ft.TextField(
        label="Name *",
        hint_text="e.g. Amlodipine",
        value=editing_med[2] if is_editing else "",
        autofocus=True,
    )

    # Form segmented pills: Tablet, Capsule, Liquid, Injection
    selected_form = {"value": "Tablet"}
    form_buttons_row = ft.Row(spacing=8)

    def set_form(val):
        selected_form["value"] = val
        for btn in form_buttons_row.controls:
            is_active = btn.data == val
            btn.bgcolor = ft.Colors.TEAL_800 if is_active else ft.Colors.GREY_100
            btn.color = ft.Colors.WHITE if is_active else ft.Colors.GREY_800
        page.update()

    for f_label in ["Tablet", "Capsule", "Liquid", "Injection"]:
        is_active = f_label == "Tablet"
        btn = ft.Container(
            content=ft.Text(f_label, size=12, weight=ft.FontWeight.W_600),
            data=f_label,
            bgcolor=ft.Colors.TEAL_800 if is_active else ft.Colors.GREY_100,
            border_radius=10,
            padding=ft.Padding(left=14, right=14, top=8, bottom=8),
            on_click=lambda e, val=f_label: set_form(val),
        )
        form_buttons_row.controls.append(btn)

    strength_field = ft.TextField(
        label="Strength",
        hint_text="500",
        value=editing_med[3].split()[0] if is_editing and editing_med[3] else "",
        expand=2,
    )
    unit_field = ft.TextField(
        label="Unit",
        value="mg",
        expand=1,
    )

    # Recipient dropdown
    recipients = get_care_recipients_for_caregiver(user_id) if user_id else []
    recipient_options = [ft.dropdown.Option(key="self", text="Myself")]
    for r in recipients:
        recipient_options.append(ft.dropdown.Option(key=str(r[0]), text=r[2]))

    current_rec_val = "self"
    if is_editing and editing_med[7] is not None:
        current_rec_val = str(editing_med[7])

    recipient_dropdown = ft.Dropdown(
        label="For whom",
        options=recipient_options,
        value=current_rec_val,
    )

    # Schedule: How often & times
    how_often_dropdown = ft.Dropdown(
        label="How often",
        options=[
            ft.dropdown.Option("Daily"),
            ft.dropdown.Option("Twice daily"),
            ft.dropdown.Option("Three times daily"),
            ft.dropdown.Option("As needed"),
        ],
        value="Daily" if not is_editing else (editing_med[5] or "Daily"),
        expand=1,
    )
    dose_times_field = ft.TextField(
        label="Dose times",
        hint_text="e.g. 08:00 or 08:00, 20:00",
        value=editing_med[4] if is_editing else "08:00",
        expand=2,
    )

    # Food segmented choice
    selected_food = {"value": "With food"}
    food_buttons_row = ft.Row(spacing=6, wrap=True)

    def set_food(val):
        selected_food["value"] = val
        for btn in food_buttons_row.controls:
            is_active = btn.data == val
            btn.bgcolor = ft.Colors.TEAL_800 if is_active else ft.Colors.GREY_100
            btn.color = ft.Colors.WHITE if is_active else ft.Colors.GREY_800
        page.update()

    for food_opt in ["Before food", "With food", "After food", "Any time"]:
        is_active = food_opt == "With food"
        btn = ft.Container(
            content=ft.Text(food_opt, size=11, weight=ft.FontWeight.W_500),
            data=food_opt,
            bgcolor=ft.Colors.TEAL_800 if is_active else ft.Colors.GREY_100,
            border_radius=8,
            padding=ft.Padding(left=10, right=10, top=6, bottom=6),
            on_click=lambda e, val=food_opt: set_food(val),
        )
        food_buttons_row.controls.append(btn)

    # Supply: Doses in stock & Expiry
    stock_field = ft.TextField(
        label="Doses in stock",
        hint_text="e.g. 60",
        value=str(editing_med[9]) if is_editing and editing_med[9] is not None else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=1,
    )
    expiry_field = ft.TextField(
        label="Expiry date YYYY-MM-DD (optional)",
        hint_text="e.g. 2027-06-30",
        value=editing_med[10] if is_editing and editing_med[10] else "",
        expand=1,
    )

    # Reminder toggles
    push_switch = ft.Switch(label="Push notification", value=True)
    sound_switch = ft.Switch(label="Sound notification chime", value=True)

    error_text = ft.Text(value="", size=12, color=ft.Colors.RED_500)

    def handle_save(e):
        name = name_field.value.strip()
        if not name:
            error_text.value = "Please enter a medication name."
            page.update()
            return

        str_val = strength_field.value.strip()
        unit_val = unit_field.value.strip() or "mg"
        dosage = f"{str_val} {unit_val}".strip() if str_val else "Standard dose"

        raw_time = dose_times_field.value.strip()
        normalized = normalize_time(raw_time) if raw_time else None
        if not normalized:
            error_text.value = "Invalid dose times. Use format like 08:00 or 08:00, 20:00."
            page.update()
            return

        freq = how_often_dropdown.value or "Daily"
        rec_id = None if recipient_dropdown.value == "self" else int(recipient_dropdown.value)

        qty_text = stock_field.value.strip()
        qty = int(qty_text) if qty_text.isdigit() else None
        exp = expiry_field.value.strip() or None

        if is_editing:
            update_medication(med_id, name, dosage, normalized, freq, rec_id, qty, exp)
        else:
            insert_medication(user_id, name, dosage, normalized, freq, rec_id, qty, exp)

        page.pop_dialog()
        if on_saved:
            on_saved()
        page.update()

    def handle_cancel(e):
        page.pop_dialog()
        page.update()

    dialog_title = "Edit medication" if is_editing else "Add medication"
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(dialog_title, size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("Start with the basics. You can change anything later.", size=12, color=ft.Colors.GREY_600),
                    ],
                    spacing=2,
                ),
                ft.IconButton(ft.Icons.CLOSE, on_click=handle_cancel),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text("MEDICATION", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500),
                    name_field,
                    ft.Text("Form", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
                    form_buttons_row,
                    ft.Row([strength_field, unit_field]),
                    recipient_dropdown,
                    ft.Divider(height=10),
                    ft.Text("SCHEDULE", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500),
                    ft.Row([how_often_dropdown, dose_times_field]),
                    ft.Text("With food", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
                    food_buttons_row,
                    ft.Divider(height=10),
                    ft.Text("SUPPLY", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500),
                    ft.Row([stock_field, expiry_field]),
                    ft.Divider(height=10),
                    ft.Text("REMINDERS", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500),
                    push_switch,
                    sound_switch,
                    error_text,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
            ),
            width=460,
            height=520,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=handle_cancel),
            ft.Button(
                "Save medication",
                bgcolor=ft.Colors.TEAL_800,
                color=ft.Colors.WHITE,
                on_click=handle_save,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
    page.update()
