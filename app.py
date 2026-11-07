import asyncio
import os
import re
import threading
from datetime import datetime, date, timedelta
import flet as ft
from config import APP_VERSION, LOW_STOCK_THRESHOLD, EXPIRY_WARNING_DAYS, logger
from database import (
    prepare_database_location, run_all_migrations, check_database_integrity, create_database_backup,
    create_users_table, create_medications_table, create_dose_records_table,
    create_care_recipients_table, add_recipient_id_column, add_quantity_and_expiry_columns,
    create_medication_schedules_table, add_schedule_id_column_to_dose_records, migrate_comma_times_to_schedules,
    get_schedules_for_medication, get_all_schedules_for_user,
    insert_user, hash_password, login_user, get_user_by_email,
    insert_medication, insert_medications_batch, get_medications_for_user,
    insert_dose_record, get_dose_history_for_user,
    export_adherence_to_csv, get_adherence_report_data,
    update_medication, delete_medication, decrement_quantity, refill_medication,
    insert_care_recipient, update_care_recipient, delete_care_recipient, get_care_recipients_for_caregiver
)
from services.watcher import (
    _parse_single_time,
    normalize_time,
    should_alert,
    send_alert,
    start_watcher,
)
from services.adherence import format_adherence_summary
from ui.views.auth_view import build_auth_view
from ui.components import (
    show_refill_dialog,
    build_medication_card,
    build_warnings_card,
)

def main(page: ft.Page):
    page.title = "MediTrack"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 500
    page.window.height = 700

    current_user = {"id": None, "name": None, "email": None}
    already_notified_today = set()
    editing_medication_id = {"value": None}

    # Start background watcher daemon from services
    watcher_stop_event = threading.Event()
    watcher_thread, _ = start_watcher(
        current_user,
        stop_event=watcher_stop_event,
        already_notified=already_notified_today
    )

    medications_list = ft.Column()
    selected_recipient_filter = {"value": "all"}
    recipient_filter_row = ft.Row(scroll=ft.ScrollMode.AUTO, wrap=False)
    dose_history_list = ft.Column()
    warnings_list = ft.Column()
    adherence_text = ft.Text(value="")

    def refresh_dose_history():
        dose_history_list.controls.clear()
        if current_user["id"] is None:
            return
        history = get_dose_history_for_user(current_user["id"])
        for record in history:
            med_name = record[0]
            status = record[1]
            taken_at = record[2]
            sched_time = record[3] if len(record) > 3 and record[3] else None
            slot_info = f" (slot: {sched_time})" if sched_time else ""
            dose_history_list.controls.append(ft.Text(f"{taken_at} — {med_name}: {status}{slot_info}"))

    def refresh_adherence_stats():
        if current_user["id"] is None:
            adherence_text.value = ""
            return
        history = get_dose_history_for_user(current_user["id"])
        adherence_text.value = format_adherence_summary(history)

    def mark_dose(medication_id, status, schedule_id=None):
        insert_dose_record(medication_id, status, schedule_id)
        if status == "taken":
            decrement_quantity(medication_id)
        refresh_dose_history()
        refresh_adherence_stats()
        refresh_medications_list()
        refresh_warnings_list()
        page.update()

    csv_export_message = ft.Text(value="", size=12)

    def export_csv_clicked(e):
        if current_user["id"] is None:
            csv_export_message.value = "Please log in first."
            csv_export_message.color = ft.Colors.RED_500
            page.update()
            return

        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        os.makedirs(docs_dir, exist_ok=True)
        filename = f"MediTrack_Adherence_{date.today().isoformat()}.csv"
        target_path = os.path.join(docs_dir, filename)

        success, result = export_adherence_to_csv(current_user["id"], target_path)
        if success:
            csv_export_message.value = f"✓ Exported to Documents/{filename}"
            csv_export_message.color = ft.Colors.GREEN_700
        else:
            csv_export_message.value = f"Export failed: {result}"
            csv_export_message.color = ft.Colors.RED_500
        page.update()

    export_csv_button = ft.Button(
        "Export CSV",
        icon=ft.Icons.DOWNLOAD,
        on_click=export_csv_clicked
    )

    care_recipients_list = ft.Column()
    recipient_name_field = ft.TextField(label="Recipient Name")
    recipient_relationship_field = ft.TextField(label="Relationship (e.g. Mother, Father)")
    recipient_message = ft.Text(value="")
    editing_recipient_id = {"value": None}
    recipient_form_title = ft.Text("People You Care For", weight=ft.FontWeight.BOLD)
    save_recipient_button = ft.Button("Add Care Recipient")
    cancel_recipient_edit_button = ft.TextButton("Cancel", visible=False)

    more_options_visible = {"value": False}

    med_name_field = ft.TextField(label="Medication Name")
    med_dosage_field = ft.TextField(label="Dosage (e.g. 500mg)")
    med_time_field = ft.TextField(label="Time(s) (e.g. 08:00 or 08:00, 20:00)")
    med_frequency_field = ft.TextField(label="Frequency (e.g. daily)")
    med_quantity_field = ft.TextField(label="Quantity Remaining (optional)")
    med_expiry_field = ft.TextField(label="Expiry Date YYYY-MM-DD (optional)")
    recipient_dropdown = ft.Dropdown(
        label="For",
        options=[ft.dropdown.Option(key="self", text="Myself")],
        value="self",
    )
    med_message = ft.Text(value="")
    med_form_title = ft.Text("Add Medication", weight=ft.FontWeight.BOLD)
    save_medication_button = ft.Button("Add Medication")
    cancel_edit_button = ft.TextButton("Cancel", visible=False)

    more_options_container = ft.Container(
        content=ft.Column([med_quantity_field, med_expiry_field], spacing=10),
        bgcolor=ft.Colors.GREY_100,
        border_radius=10,
        padding=12,
        visible=False,
    )

    def toggle_more_options(e):
        more_options_container.visible = not more_options_container.visible
        more_options_toggle.text = "Less options ▴" if more_options_container.visible else "More options ▾"
        page.update()

    more_options_toggle = ft.TextButton("More options ▾", on_click=toggle_more_options)

    def get_recipient_options():
        recipients = get_care_recipients_for_caregiver(current_user["id"]) if current_user["id"] else []
        options = [ft.dropdown.Option(key="self", text="Myself")]
        for recipient in recipients:
            options.append(ft.dropdown.Option(key=str(recipient[0]), text=recipient[2]))
        return options

    def refresh_recipient_dropdown():
        options = get_recipient_options()
        recipient_dropdown.options = options
        for row_box in batch_rows_column.controls:
            if hasattr(row_box, "data") and "recipient" in row_box.data:
                row_box.data["recipient"].options = options

    batch_rows_column = ft.Column(spacing=10)
    batch_message = ft.Text(value="")

    def create_batch_row():
        row_name = ft.TextField(label="Medication Name", expand=2)
        row_dosage = ft.TextField(label="Dosage (e.g. 500mg)", expand=1)
        row_time = ft.TextField(label="Time(s) (e.g. 08:00, 20:00)", expand=2)
        row_freq = ft.TextField(label="Frequency", value="daily", expand=1)
        row_recipient = ft.Dropdown(
            label="For",
            options=get_recipient_options(),
            value="self",
            expand=1,
        )

        row_container = ft.Container()

        def remove_row(e):
            if len(batch_rows_column.controls) > 1:
                batch_rows_column.controls.remove(row_container)
                page.update()
            else:
                batch_message.value = "At least one medication row is required in batch mode."
                batch_message.color = ft.Colors.RED_600
                page.update()

        remove_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="Remove this row",
            on_click=remove_row,
        )

        row_container.content = ft.Column(
            [
                ft.Row([row_name, row_dosage, remove_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([row_time, row_freq, row_recipient]),
            ],
            spacing=8,
        )
        row_container.bgcolor = ft.Colors.GREY_50
        row_container.border = ft.Border.all(1, ft.Colors.GREY_300)
        row_container.border_radius = 8
        row_container.padding = 10
        row_container.data = {
            "name": row_name,
            "dosage": row_dosage,
            "time": row_time,
            "freq": row_freq,
            "recipient": row_recipient,
        }
        return row_container

    def add_batch_row_clicked(e):
        batch_rows_column.controls.append(create_batch_row())
        page.update()

    def save_batch_clicked(e):
        if current_user["id"] is None:
            batch_message.value = "Please log in first."
            batch_message.color = ft.Colors.RED_600
            page.update()
            return

        to_insert = []
        row_num = 1
        for row_box in batch_rows_column.controls:
            data = row_box.data
            name = data["name"].value.strip() if data["name"].value else ""
            dosage = data["dosage"].value.strip() if data["dosage"].value else ""
            raw_time = data["time"].value.strip() if data["time"].value else ""
            freq = data["freq"].value.strip() if data["freq"].value else ""
            rec_val = data["recipient"].value

            # If row is completely blank, skip it
            if not name and not dosage and not raw_time and not freq:
                row_num += 1
                continue

            if not name or not dosage or not raw_time or not freq:
                batch_message.value = f"Row {row_num}: Please fill in name, dosage, time, and frequency."
                batch_message.color = ft.Colors.RED_600
                page.update()
                return

            normalized_time = normalize_time(raw_time)
            if not normalized_time:
                batch_message.value = f"Row {row_num} ('{name}'): Invalid time '{raw_time}'. Use e.g. 08:30 or 08:00, 20:00."
                batch_message.color = ft.Colors.RED_600
                page.update()
                return

            recipient_id = None if rec_val == "self" else int(rec_val)
            to_insert.append((name, dosage, normalized_time, freq, recipient_id, None, None))
            row_num += 1

        if not to_insert:
            batch_message.value = "Please enter at least one medication."
            batch_message.color = ft.Colors.RED_600
            page.update()
            return

        insert_medications_batch(current_user["id"], to_insert)
        batch_message.value = f"Successfully added {len(to_insert)} medication{'s' if len(to_insert) != 1 else ''}!"
        batch_message.color = ft.Colors.GREEN_700

        # Reset batch rows with 2 fresh rows
        batch_rows_column.controls.clear()
        batch_rows_column.controls.append(create_batch_row())
        batch_rows_column.controls.append(create_batch_row())

        refresh_medications_list()
        refresh_warnings_list()
        page.update()

    def switch_to_batch_mode(e):
        if editing_medication_id["value"] is not None:
            exit_edit_mode()
        if len(batch_rows_column.controls) == 0:
            batch_rows_column.controls.append(create_batch_row())
            batch_rows_column.controls.append(create_batch_row())
        batch_message.value = ""
        single_med_container.visible = False
        batch_med_container.visible = True
        page.update()

    def switch_to_single_mode(e):
        med_message.value = ""
        single_med_container.visible = True
        batch_med_container.visible = False
        page.update()

    batch_switch_button = ft.TextButton("➕ Switch to Batch Add", on_click=switch_to_batch_mode)

    def enter_recipient_edit_mode(recipient):
        editing_recipient_id["value"] = recipient[0]
        recipient_name_field.value = recipient[2]
        recipient_relationship_field.value = recipient[3]
        recipient_form_title.value = f"Editing: {recipient[2]}"
        save_recipient_button.text = "Update Care Recipient"
        cancel_recipient_edit_button.visible = True
        recipient_message.value = ""
        page.update()

    def exit_recipient_edit_mode():
        editing_recipient_id["value"] = None
        recipient_name_field.value = ""
        recipient_relationship_field.value = ""
        recipient_form_title.value = "People You Care For"
        save_recipient_button.text = "Add Care Recipient"
        cancel_recipient_edit_button.visible = False
        recipient_message.value = ""

    def cancel_recipient_edit_clicked(e):
        exit_recipient_edit_mode()
        page.update()

    def delete_recipient_clicked(recipient_id):
        delete_care_recipient(recipient_id)
        if editing_recipient_id["value"] == recipient_id:
            exit_recipient_edit_mode()
        refresh_care_recipients_list()
        refresh_recipient_dropdown()
        refresh_medications_list()
        page.update()

    def save_recipient_clicked(e):
        if current_user["id"] is None:
            recipient_message.value = "Please log in first."
            page.update()
            return

        name = recipient_name_field.value.strip() if recipient_name_field.value else ""
        relationship = recipient_relationship_field.value.strip() if recipient_relationship_field.value else ""

        if not name or not relationship:
            recipient_message.value = "Please enter both name and relationship."
            page.update()
            return

        if editing_recipient_id["value"] is None:
            insert_care_recipient(current_user["id"], name, relationship)
            recipient_message.value = f"Added {name} as a care recipient."
            recipient_name_field.value = ""
            recipient_relationship_field.value = ""
        else:
            update_care_recipient(editing_recipient_id["value"], name, relationship)
            recipient_message.value = f"Updated {name}."
            exit_recipient_edit_mode()

        refresh_care_recipients_list()
        refresh_recipient_dropdown()
        refresh_medications_list()
        page.update()

    save_recipient_button.on_click = save_recipient_clicked
    cancel_recipient_edit_button.on_click = cancel_recipient_edit_clicked

    def refresh_care_recipients_list():
        care_recipients_list.controls.clear()
        if current_user["id"] is None:
            return
        recipients = get_care_recipients_for_caregiver(current_user["id"])
        if not recipients:
            care_recipients_list.controls.append(
                ft.Text("No care recipients added yet.", size=12, color=ft.Colors.GREY_600)
            )
            return

        for recipient in recipients:
            rec_id = recipient[0]
            rec_name = recipient[2]
            rec_rel = recipient[3]

            edit_rec_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.GREY_500,
                tooltip="Edit recipient",
                on_click=lambda e, r=recipient: enter_recipient_edit_mode(r),
            )
            delete_rec_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete recipient",
                on_click=lambda e, rid=rec_id: delete_recipient_clicked(rid),
            )

            rec_card = ft.Container(
                content=ft.Row(
                    [
                        ft.Text("👤", size=18),
                        ft.Column(
                            [
                                ft.Text(rec_name, size=14, weight=ft.FontWeight.W_500),
                                ft.Text(rec_rel, size=12, color=ft.Colors.GREY_600),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        edit_rec_btn,
                        delete_rec_btn,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.WHITE,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                padding=12,
                margin=ft.Margin.only(bottom=8),
            )
            care_recipients_list.controls.append(rec_card)

    def enter_edit_mode(med):
        switch_to_single_mode(None)
        batch_switch_button.visible = False
        editing_medication_id["value"] = med[0]
        med_name_field.value = med[2]
        med_dosage_field.value = med[3]
        med_time_field.value = normalize_time(med[4]) or med[4]
        med_frequency_field.value = med[5]
        med_form_title.value = f"Editing: {med[2]}"
        save_medication_button.text = "Update Medication"
        cancel_edit_button.visible = True
        recipient_id = med[7]
        recipient_dropdown.value = "self" if recipient_id is None else str(recipient_id)
        med_quantity_field.value = str(med[9]) if med[9] is not None else ""
        med_expiry_field.value = med[10] if med[10] else ""
        page.update()

    def exit_edit_mode():
        editing_medication_id["value"] = None
        med_name_field.value = ""
        med_dosage_field.value = ""
        med_time_field.value = ""
        med_frequency_field.value = ""
        med_quantity_field.value = ""
        med_expiry_field.value = ""
        med_form_title.value = "Add Medication"
        save_medication_button.text = "Add Medication"
        cancel_edit_button.visible = False
        batch_switch_button.visible = True
        recipient_dropdown.value = "self"
        more_options_container.visible = False
        more_options_toggle.text = "More options ▾"

    def cancel_edit_clicked(e):
        exit_edit_mode()
        page.update()

    def delete_clicked(medication_id):
        delete_medication(medication_id)
        if editing_medication_id["value"] == medication_id:
            exit_edit_mode()
        refresh_medications_list()
        refresh_warnings_list()
        page.update()

    def refill_clicked(med_id, med_name, current_qty):
        show_refill_dialog(
            page,
            med_id,
            med_name,
            current_qty,
            on_refill_success=lambda: (refresh_medications_list(), refresh_warnings_list())
        )

    def set_recipient_filter(val):
        selected_recipient_filter["value"] = val
        refresh_medications_list()
        page.update()

    def refresh_medications_list():
        medications_list.controls.clear()
        recipient_filter_row.controls.clear()
        if current_user["id"] is None:
            return

        # Build filter chips
        recipients = get_care_recipients_for_caregiver(current_user["id"])
        filter_options = [("all", "All"), ("self", "Myself")]
        for r in recipients:
            filter_options.append((str(r[0]), r[2]))

        for f_val, f_label in filter_options:
            is_selected = selected_recipient_filter["value"] == f_val
            chip = ft.Container(
                content=ft.Text(
                    f_label,
                    size=12,
                    weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                    color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_800,
                ),
                bgcolor=ft.Colors.BLUE_600 if is_selected else ft.Colors.GREY_200,
                border_radius=16,
                padding=ft.Padding(left=12, right=12, top=6, bottom=6),
                on_click=lambda e, val=f_val: set_recipient_filter(val),
            )
            recipient_filter_row.controls.append(chip)

        meds = get_medications_for_user(current_user["id"])

        # Filter medications based on active chip
        filtered_meds = []
        for med in meds:
            rec_id = med[7]
            if selected_recipient_filter["value"] == "all":
                filtered_meds.append(med)
            elif selected_recipient_filter["value"] == "self" and rec_id is None:
                filtered_meds.append(med)
            elif str(rec_id) == str(selected_recipient_filter["value"]):
                filtered_meds.append(med)

        if not filtered_meds:
            medications_list.controls.append(
                ft.Container(
                    content=ft.Text("No medications match this filter.", size=13, italic=True, color=ft.Colors.GREY_500),
                    padding=10,
                )
            )
            return

        for med in filtered_meds:
            card = build_medication_card(
                med=med,
                on_take=lambda mid: mark_dose(mid, "taken"),
                on_skip=lambda mid: mark_dose(mid, "skipped"),
                on_refill=lambda mid, mname, mqty: refill_clicked(mid, mname, mqty),
                on_edit=lambda m: enter_edit_mode(m),
                on_delete=lambda mid: delete_clicked(mid),
            )
            medications_list.controls.append(card)

    def refresh_warnings_list():
        warnings_list.controls.clear()
        if current_user["id"] is None:
            return
        meds = get_medications_for_user(current_user["id"])
        card = build_warnings_card(
            meds,
            low_stock_threshold=LOW_STOCK_THRESHOLD,
            expiry_warning_days=EXPIRY_WARNING_DAYS,
        )
        if card:
            warnings_list.controls.append(card)

    def save_medication_clicked(e):
        if current_user["id"] is None:
            med_message.value = "Please log in first."
            page.update()
            return

        name = med_name_field.value
        dosage = med_dosage_field.value
        raw_time = med_time_field.value
        frequency = med_frequency_field.value

        if not name or not dosage or not raw_time or not frequency:
            med_message.value = "Please fill in all medication fields."
            page.update()
            return

        time = normalize_time(raw_time)
        if not time:
            med_message.value = "Invalid time format. Please use e.g. 08:30 or 2:30 PM."
            page.update()
            return

        selected = recipient_dropdown.value
        recipient_id = None if selected == "self" else int(selected)

        quantity_text = med_quantity_field.value
        quantity_remaining = int(quantity_text) if quantity_text.strip() else None

        expiry_date = med_expiry_field.value.strip() or None

        if editing_medication_id["value"] is None:
            insert_medication(current_user["id"], name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
            med_message.value = f"Added {name}."
        else:
            update_medication(editing_medication_id["value"], name, dosage, time, frequency, recipient_id, quantity_remaining, expiry_date)
            med_message.value = f"Updated {name}."
            exit_edit_mode()

        refresh_medications_list()
        refresh_warnings_list()
        page.update()

    save_medication_button.on_click = save_medication_clicked
    cancel_edit_button.on_click = cancel_edit_clicked

    single_med_container = ft.Container(
        content=ft.Column(
            [
                ft.Row([med_form_title, batch_switch_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                med_name_field, med_dosage_field, med_time_field, med_frequency_field,
                recipient_dropdown,
                more_options_toggle,
                more_options_container,
                ft.Row([save_medication_button, cancel_edit_button]),
                med_message,
            ],
            spacing=10,
        ),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=12,
        padding=16,
    )

    batch_med_container = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Batch Add Medications", weight=ft.FontWeight.BOLD, size=16),
                                ft.Text("Add multiple drugs at once. Times can be e.g. 08:00, 20:00", size=12, color=ft.Colors.GREY_600),
                            ],
                            spacing=2,
                        ),
                        ft.TextButton("Single Add Mode", on_click=switch_to_single_mode),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                batch_rows_column,
                ft.Row(
                    [
                        ft.Button("+ Add Another Drug", icon=ft.Icons.ADD, on_click=add_batch_row_clicked),
                        ft.Button("Save All Medications", icon=ft.Icons.CHECK, on_click=save_batch_clicked),
                    ],
                    spacing=10,
                ),
                batch_message,
            ],
            spacing=12,
        ),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=12,
        padding=16,
        visible=False,
    )

    def on_login_success(user):
        current_user["id"] = user[0]
        current_user["name"] = user[1]
        current_user["email"] = user[2]
        refresh_medications_list()
        refresh_dose_history()
        refresh_adherence_stats()
        refresh_care_recipients_list()
        refresh_recipient_dropdown()
        refresh_warnings_list()
        asyncio.create_task(page.push_route("/dashboard"))

    def logout_clicked(e):
        current_user["id"] = None
        current_user["name"] = None
        current_user["email"] = None
        exit_edit_mode()
        exit_recipient_edit_mode()
        asyncio.create_task(page.push_route("/"))

    def route_change(e):
        page.views.clear()

        if page.route == "/":
            page.views.append(build_auth_view(page, on_login_success=on_login_success))
        elif page.route == "/dashboard":
            if current_user["id"] is None:
                asyncio.create_task(page.push_route("/"))
                return

            page.views.append(
                ft.View(
                    route="/dashboard",
                    controls=[
                        ft.Row(
                            [
                                ft.Text(f"Welcome, {current_user['name']}", size=22, weight=ft.FontWeight.BOLD),
                                ft.TextButton("Log out", on_click=logout_clicked),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Text("Warnings", weight=ft.FontWeight.BOLD),
                        warnings_list,
                        ft.Divider(),
                        single_med_container,
                        batch_med_container,
                        ft.Divider(),
                        ft.Text("My Medications", weight=ft.FontWeight.BOLD),
                        recipient_filter_row,
                        medications_list,
                        ft.Divider(),
                        ft.Row(
                            [
                                ft.Text("Dose History", weight=ft.FontWeight.BOLD, size=16),
                                export_csv_button,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        adherence_text,
                        csv_export_message,
                        dose_history_list,
                        ft.Divider(),
                        ft.Container(
                            content=ft.Column(
                                [
                                    recipient_form_title,
                                    recipient_name_field,
                                    recipient_relationship_field,
                                    ft.Row([save_recipient_button, cancel_recipient_edit_button]),
                                    recipient_message,
                                ],
                                spacing=10,
                            ),
                            bgcolor=ft.Colors.WHITE,
                            border=ft.Border.all(1, ft.Colors.GREY_300),
                            border_radius=12,
                            padding=16,
                        ),
                        care_recipients_list,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            )

        page.update()

    page.on_route_change = route_change
    route_change(None)

if __name__ == "__main__":
    logger.info(f"Starting MediTrack v{APP_VERSION}...")
    prepare_database_location()  # Creates AppData folders, migrates legacy DB, creates baseline backup
    run_all_migrations()         # Version-controlled sequential migrations
    is_ok, check_msgs = check_database_integrity()
    if is_ok:
        logger.info("Database integrity check passed.")
    else:
        logger.warning(f"Database integrity warning: {check_msgs}")
    ft.run(main)