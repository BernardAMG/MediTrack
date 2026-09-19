import asyncio
import threading
from datetime import datetime, date, timedelta
from plyer import notification
import flet as ft
from database import (
    create_users_table, create_medications_table, create_dose_records_table,
    create_care_recipients_table, add_recipient_id_column, add_quantity_and_expiry_columns,
    insert_user, hash_password, login_user, get_user_by_email,
    insert_medication, get_medications_for_user,
    insert_dose_record, get_dose_history_for_user,
    update_medication, delete_medication, decrement_quantity,
    insert_care_recipient, get_care_recipients_for_caregiver
)

LOW_STOCK_THRESHOLD = 5
EXPIRY_WARNING_DAYS = 30

def main(page: ft.Page):
    page.title = "MediTrack"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 500
    page.window.height = 700

    current_user = {"id": None, "name": None, "email": None}
    already_notified_today = set()
    editing_medication_id = {"value": None}

    def send_alert(med):
        title = "MediTrack Reminder"
        message_text = f"Time to take {med[2]} ({med[3]})"
        try:
            notification.notify(title=title, message=message_text, timeout=10)
        except Exception:
            print(f"🔔 {title}: {message_text}")

    def watcher_loop(stop_event):
        while not stop_event.is_set():
            if current_user["id"] is not None:
                now_str = datetime.now().strftime("%H:%M")
                meds = get_medications_for_user(current_user["id"])
                for med in meds:
                    key = (med[0], med[4])
                    if med[4] == now_str and key not in already_notified_today:
                        send_alert(med)
                        already_notified_today.add(key)
            stop_event.wait(30)

    watcher_stop_event = threading.Event()
    watcher_thread = threading.Thread(target=watcher_loop, args=(watcher_stop_event,), daemon=True)
    watcher_thread.start()

    medications_list = ft.Column()
    dose_history_list = ft.Column()
    warnings_list = ft.Column()
    adherence_text = ft.Text(value="")

    def refresh_dose_history():
        dose_history_list.controls.clear()
        if current_user["id"] is None:
            return
        history = get_dose_history_for_user(current_user["id"])
        for record in history:
            med_name, status, taken_at = record
            dose_history_list.controls.append(ft.Text(f"{taken_at} — {med_name}: {status}"))

    def refresh_adherence_stats():
        if current_user["id"] is None:
            adherence_text.value = ""
            return
        history = get_dose_history_for_user(current_user["id"])
        total = len(history)
        if total == 0:
            adherence_text.value = "No doses logged yet."
            return
        taken_count = sum(1 for record in history if record[1] == "taken")
        percentage = round((taken_count / total) * 100)
        adherence_text.value = f"{percentage}% adherence ({taken_count} of {total} doses taken)"

    def mark_dose(medication_id, status):
        insert_dose_record(medication_id, status)
        if status == "taken":
            decrement_quantity(medication_id)
        refresh_dose_history()
        refresh_adherence_stats()
        refresh_medications_list()
        refresh_warnings_list()
        page.update()

    care_recipients_list = ft.Column()
    recipient_name_field = ft.TextField(label="Recipient Name")
    recipient_relationship_field = ft.TextField(label="Relationship (e.g. Mother, Father)")
    recipient_message = ft.Text(value="")

    more_options_visible = {"value": False}

    med_name_field = ft.TextField(label="Medication Name")
    med_dosage_field = ft.TextField(label="Dosage (e.g. 500mg)")
    med_time_field = ft.TextField(label="Time (HH:MM)")
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

    def refresh_recipient_dropdown():
        recipients = get_care_recipients_for_caregiver(current_user["id"]) if current_user["id"] else []
        options = [ft.dropdown.Option(key="self", text="Myself")]
        for recipient in recipients:
            options.append(ft.dropdown.Option(key=str(recipient[0]), text=recipient[2]))
        recipient_dropdown.options = options

    def refresh_care_recipients_list():
        care_recipients_list.controls.clear()
        if current_user["id"] is None:
            return
        recipients = get_care_recipients_for_caregiver(current_user["id"])
        for recipient in recipients:
            care_recipients_list.controls.append(
                ft.Text(f"{recipient[2]} ({recipient[3]})")
            )

    def add_recipient_clicked(e):
        if current_user["id"] is None:
            recipient_message.value = "Please log in first."
            page.update()
            return

        name = recipient_name_field.value
        relationship = recipient_relationship_field.value

        if not name or not relationship:
            recipient_message.value = "Please enter both name and relationship."
            page.update()
            return

        insert_care_recipient(current_user["id"], name, relationship)
        recipient_message.value = f"Added {name} as a care recipient."
        recipient_name_field.value = ""
        recipient_relationship_field.value = ""
        refresh_care_recipients_list()
        refresh_recipient_dropdown()
        page.update()

    def enter_edit_mode(med):
        editing_medication_id["value"] = med[0]
        med_name_field.value = med[2]
        med_dosage_field.value = med[3]
        med_time_field.value = med[4]
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

    def refresh_medications_list():
        medications_list.controls.clear()
        if current_user["id"] is None:
            return
        meds = get_medications_for_user(current_user["id"])
        for med in meds:
            med_id = med[0]
            for_text = f" for {med[8]}" if med[8] else " for myself"
            time_text = f"{med[4]}{for_text}"

            take_button = ft.IconButton(
                icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                icon_color=ft.Colors.GREEN_600,
                on_click=lambda e, mid=med_id: mark_dose(mid, "taken"),
            )
            skip_button = ft.IconButton(
                icon=ft.Icons.CANCEL_OUTLINED,
                icon_color=ft.Colors.GREY_500,
                on_click=lambda e, mid=med_id: mark_dose(mid, "skipped"),
            )
            edit_button = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.GREY_500,
                on_click=lambda e, m=med: enter_edit_mode(m),
            )
            delete_button = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                on_click=lambda e, mid=med_id: delete_clicked(mid),
            )

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Text("💊", size=18),
                        ft.Column(
                            [
                                ft.Text(f"{med[2]} · {med[3]}", size=14, weight=ft.FontWeight.W_500),
                                ft.Text(time_text, size=12, color=ft.Colors.GREY_600),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        take_button,
                        skip_button,
                        edit_button,
                        delete_button,
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
            medications_list.controls.append(card)

    def refresh_warnings_list():
        warnings_list.controls.clear()
        if current_user["id"] is None:
            return
        meds = get_medications_for_user(current_user["id"])
        today = date.today()
        warning_lines = []

        for med in meds:
            name = med[2]
            quantity = med[9]
            expiry_str = med[10]

            if quantity is not None and quantity <= LOW_STOCK_THRESHOLD:
                warning_lines.append(f"{name}: only {quantity} left")

            if expiry_str:
                try:
                    expiry = date.fromisoformat(expiry_str)
                    days_left = (expiry - today).days
                    if days_left < 0:
                        warning_lines.append(f"{name}: expired on {expiry_str}")
                    elif days_left <= EXPIRY_WARNING_DAYS:
                        warning_lines.append(f"{name}: expires in {days_left} days ({expiry_str})")
                except ValueError:
                    pass

        if not warning_lines:
            return

        header = ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.ORANGE_800, size=16),
                ft.Text(f"{len(warning_lines)} warning{'s' if len(warning_lines) != 1 else ''}",
                        size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ORANGE_800),
            ],
            spacing=6,
        )

        lines = [ft.Text(line, size=13, color=ft.Colors.ORANGE_800) for line in warning_lines]

        card = ft.Container(
            content=ft.Column([header] + lines, spacing=4),
            bgcolor=ft.Colors.ORANGE_50,
            border_radius=12,
            padding=14,
        )
        warnings_list.controls.append(card)

    def save_medication_clicked(e):
        if current_user["id"] is None:
            med_message.value = "Please log in first."
            page.update()
            return

        name = med_name_field.value
        dosage = med_dosage_field.value
        time = med_time_field.value
        frequency = med_frequency_field.value

        if not name or not dosage or not time or not frequency:
            med_message.value = "Please fill in all medication fields."
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

    name_field = ft.TextField(label="Name")
    email_field = ft.TextField(label="Email")
    password_field = ft.TextField(label="Password", password=True)
    register_message = ft.Text(value="")

    def register_clicked(e):
        name = name_field.value
        email = email_field.value
        password = password_field.value
        if not name or not email or not password:
            register_message.value = "Please fill in all fields."
            page.update()
            return
        hashed = hash_password(password)
        success, result_message = insert_user(name, email, hashed)
        register_message.value = result_message
        page.update()

    login_email_field = ft.TextField(label="Login Email")
    login_password_field = ft.TextField(label="Login Password", password=True)
    login_message = ft.Text(value="")

    def login_clicked(e):
        email = login_email_field.value
        password = login_password_field.value
        if not email or not password:
            login_message.value = "Please enter email and password."
            page.update()
            return
        success, result_message = login_user(email, password)
        login_message.value = result_message
        page.update()
        if success:
            user = get_user_by_email(email)
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
        asyncio.create_task(page.push_route("/"))

    def route_change(e):
        page.views.clear()

        if page.route == "/":
            page.views.append(
                ft.View(
                    route="/",
                    controls=[
                        ft.Text("MediTrack", size=28, weight=ft.FontWeight.BOLD),
                        ft.Text("Register", weight=ft.FontWeight.BOLD),
                        name_field, email_field, password_field,
                        ft.Button("Register", on_click=register_clicked),
                        register_message,
                        ft.Divider(),
                        ft.Text("Login", weight=ft.FontWeight.BOLD),
                        login_email_field, login_password_field,
                        ft.Button("Login", on_click=login_clicked),
                        login_message,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            )
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
                        ft.Container(
                            content=ft.Column(
                                [
                                    med_form_title,
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
                        ),
                        ft.Divider(),
                        ft.Text("My Medications", weight=ft.FontWeight.BOLD),
                        medications_list,
                        ft.Divider(),
                        ft.Text("Dose History", weight=ft.FontWeight.BOLD),
                        adherence_text,
                        dose_history_list,
                        ft.Divider(),
                        ft.Text("People You Care For", weight=ft.FontWeight.BOLD),
                        recipient_name_field, recipient_relationship_field,
                        ft.Button("Add Care Recipient", on_click=add_recipient_clicked),
                        recipient_message,
                        care_recipients_list,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            )

        page.update()

    page.on_route_change = route_change
    route_change(None)

create_users_table()
create_medications_table()
create_dose_records_table()
create_care_recipients_table()
add_recipient_id_column()
add_quantity_and_expiry_columns()
ft.run(main)