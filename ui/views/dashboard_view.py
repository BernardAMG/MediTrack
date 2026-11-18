"""
ui/views/dashboard_view.py
Faithful desktop implementation of the "Your Daily Health Partner" card-based interface.
Features:
- Warm sage neutral background (#F2F4F0), crisp white rounded cards (border_radius=22),
  rich sage green (#52734D) accents, and deep forest typography (#182418)
- Header with user avatar, brand identity, and Dark/Light Mode accessibility toggle
- Category filter pills: All Medicines, Due Today, Low Stock, Schedule Timeline, Dose History, Settings
- "Your Digital Medicine" Next Scheduled Dose Hero Card (matching Screen 1 & 3 in the reference)
- Medication Card Grid (matching the product cards in Screen 2) with pill form tags,
  medicine bottle avatar, stock indicator, Take Dose pill, and Edit / Refill / Delete actions
- Floating quick-action dock: Refill Supply, Add Medication, Export Adherence Report
- Full CRUD operations and clinical doctor-ready CSV adherence export
"""
import os
import re
from datetime import datetime, date
import flet as ft
from config import LOW_STOCK_THRESHOLD, EXPIRY_WARNING_DAYS
from database import (
    get_medications_for_user,
    get_schedules_for_medication,
    get_dose_history_for_user,
    insert_dose_record,
    decrement_quantity,
    delete_medication,
    insert_medication,
    export_adherence_to_csv,
    get_care_recipients_for_caregiver,
    insert_care_recipient,
    update_care_recipient,
    delete_care_recipient,
    create_database_backup,
    vacuum_database,
)
from services.watcher import normalize_time
from services.adherence import calculate_adherence_stats
from ui.components.refill_dialog import show_refill_dialog
from ui.components.medication_drawer import show_medication_drawer
from ui.components.delete_dialog import (
    show_delete_medication_dialog,
    show_delete_recipient_dialog,
)
from ui.theme import AppTheme

def build_dashboard_view(page: ft.Page, current_user: dict, on_logout=None):
    """
    Constructs the desktop dashboard matching 'Your Daily Health Partner' design.
    """
    user_id = current_user["id"]
    user_name = current_user.get("name") or "User"
    initials = "".join([part[0].upper() for part in user_name.split()[:2]]) or "U"

    # View & Navigation state
    active_nav = {"current": "today"}  # 'today', 'meds', 'schedule', 'history', 'settings'
    med_filter = {"value": "all"}       # 'all' or 'low'
    search_query = {"value": ""}
    banner_dismissed = {"value": False}
    med_list_cache = {"meds": []}

    # Dynamic containers
    main_workspace_container = ft.Container(expand=True)
    banner_container = ft.Container()
    category_pills_container = ft.Container()
    global_snack_text = ft.Text(value="", size=12)

    # Theme toggle callback
    def toggle_theme_mode(e=None):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        refresh_all()
        page.update()

    # Core Action Callbacks
    def mark_dose(med_id, status, sched_id=None):
        insert_dose_record(med_id, status, sched_id)
        if status == "taken":
            decrement_quantity(med_id)
        refresh_all()
        page.update()

    def handle_refill(med_id, name, current_qty):
        show_refill_dialog(page, med_id, name, current_qty, on_refill_success=refresh_all)

    def handle_edit(med):
        show_medication_drawer(page, user_id, editing_med=med, on_saved=refresh_all)

    def handle_delete(med_id, name):
        show_delete_medication_dialog(page, med_id, name, on_deleted=refresh_all)

    def handle_open_add_drawer(e=None):
        show_medication_drawer(page, user_id, editing_med=None, on_saved=refresh_all)

    def handle_export_csv(e=None):
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        theme = AppTheme(is_dark)
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        os.makedirs(docs_dir, exist_ok=True)
        filename = f"MediTrack_Adherence_{date.today().isoformat()}.csv"
        target_path = os.path.join(docs_dir, filename)
        success, msg = export_adherence_to_csv(user_id, target_path)
        if success:
            global_snack_text.value = f"✓ Exported to Documents/{filename}"
            global_snack_text.color = theme.primary
        else:
            global_snack_text.value = f"Export failed: {msg}"
            global_snack_text.color = ft.Colors.RED_600
        page.update()

    # Helper: Build Medication Product Card (Image 2 style)
    def build_medication_card(med, theme, on_take_action=None):
        mid = med[0]
        mname = med[2]
        mdose = med[3]
        mtimes = med[4]
        mfreq = med[5] or "Daily"
        rec_name = med[8] or "Myself"
        mqty = med[9]
        mexp = med[10] or "Not specified"
        is_low = mqty is not None and mqty <= LOW_STOCK_THRESHOLD

        # Form icon detection
        f_lower = mdose.lower() + " " + mname.lower()
        if "liquid" in f_lower or "syrup" in f_lower or "ml" in f_lower:
            form_icon = "🧴"
            form_tag = "Liquid"
        elif "injection" in f_lower or "shot" in f_lower or "insulin" in f_lower:
            form_icon = "💉"
            form_tag = "Injection"
        elif "capsule" in f_lower or "cap" in f_lower:
            form_icon = "💊"
            form_tag = "Capsule"
        else:
            form_icon = "💊"
            form_tag = "Tablet"

        return ft.Container(
            content=ft.Column(
                [
                    # Top Badge Pill (Form / Time / Status)
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(form_tag, size=10, weight=ft.FontWeight.BOLD, color=theme.tag_text),
                                bgcolor=theme.tag_bg,
                                border_radius=12,
                                padding=ft.Padding(10, 4, 10, 4),
                            ),
                            ft.Container(
                                content=ft.Text(f"👤 {rec_name}", size=10, color=theme.text_muted),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=4),
                    # Center Medicine Bottle Avatar
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(form_icon, size=32),
                                bgcolor=theme.surface_alt,
                                border_radius=30,
                                width=60,
                                height=60,
                                alignment=ft.Alignment(0, 0),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Container(height=4),
                    # Medication Title
                    ft.Text(
                        mname,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color=theme.text_primary,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    # Dosage & Schedule
                    ft.Text(
                        f"{mdose} · {mfreq}",
                        size=11,
                        color=theme.text_secondary,
                    ),
                    # Supply Pill / Alert
                    ft.Row(
                        [
                            ft.Text(
                                f"{mqty if mqty is not None else '30'} doses left",
                                size=11,
                                weight=ft.FontWeight.BOLD if is_low else ft.FontWeight.W_500,
                                color=theme.banner_text if is_low else theme.text_muted,
                            ),
                            ft.Container(
                                content=ft.Text(mtimes, size=10, color=theme.primary, weight=ft.FontWeight.BOLD),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=10, color=theme.border),
                    # Action Row: Take Dose Button + Edit + Refill + Delete
                    ft.Row(
                        [
                            ft.Button(
                                "Take now",
                                bgcolor=theme.primary,
                                color=ft.Colors.WHITE,
                                height=34,
                                border_radius=17,
                                expand=1,
                                on_click=lambda e, mid=mid: (mark_dose(mid, "taken")),
                            ),
                            ft.IconButton(
                                ft.Icons.EDIT_OUTLINED,
                                icon_size=16,
                                icon_color=theme.primary,
                                tooltip="Edit details",
                                on_click=lambda e, m=med: handle_edit(m),
                            ),
                            ft.IconButton(
                                ft.Icons.ADD_SHOPPING_CART_OUTLINED,
                                icon_size=16,
                                icon_color=theme.primary,
                                tooltip="Log refill",
                                on_click=lambda e, m=med: handle_refill(m[0], m[2], m[9]),
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=16,
                                icon_color=ft.Colors.RED_500,
                                tooltip="Delete",
                                on_click=lambda e, mid=mid, mname=mname: handle_delete(mid, mname),
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=4,
            ),
            bgcolor=theme.surface,
            border=ft.Border.all(1, theme.border),
            border_radius=22,
            padding=16,
            width=260,
        )

    # 1. VIEW BUILDER: TODAY (Your Daily Health Partner Dashboard)
    def render_today_view(meds, history, low_stock_meds, today_slots, next_candidate, theme):
        is_dark = theme.is_dark
        today_str = date.today().isoformat()

        # Build NEXT DOSE Hero Card ("Your Digital Medicine" style from Screen 1 & 3)
        if next_candidate:
            next_time, next_med = next_candidate
            next_hero = ft.Container(
                content=ft.Row(
                    [
                        # Left details
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("YOUR DIGITAL MEDICINE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                                        ft.Container(
                                            content=ft.Text("Next Dose Due", size=10, weight=ft.FontWeight.BOLD, color="#1B3A25"),
                                            bgcolor="#E5EDE2",
                                            border_radius=8,
                                            padding=ft.Padding(8, 2, 8, 2),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(next_med[2], size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{next_med[3]}  ·  For: {next_med[8] or 'Myself'}", size=12, color=ft.Colors.WHITE70),
                                ft.Container(
                                    content=ft.Row([ft.Text("🕒", size=12), ft.Text(f"Scheduled at {next_time}", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], spacing=6),
                                    bgcolor=ft.Colors.BLACK26,
                                    border_radius=12,
                                    padding=ft.Padding(10, 4, 10, 4),
                                ),
                                ft.Row(
                                    [
                                        ft.Button(
                                            "Take dose now",
                                            bgcolor=ft.Colors.WHITE,
                                            color=theme.primary_dark if not is_dark else "#111C14",
                                            height=36,
                                            border_radius=18,
                                            on_click=lambda e, mid=next_med[0]: mark_dose(mid, "taken"),
                                        ),
                                        ft.OutlinedButton(
                                            "Snooze 10 min",
                                            height=36,
                                            border_radius=18,
                                            on_click=lambda e: (page.show_snack_bar(ft.SnackBar(ft.Text("Snoozed 10 mins"))), page.update()) if hasattr(page, "show_snack_bar") else None,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=8,
                            expand=True,
                        ),
                        # Right bottle graphic
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text("🧴", size=54),
                                    ft.Text("fridays / meditrack", size=10, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                            bgcolor=ft.Colors.WHITE10,
                            border_radius=18,
                            padding=16,
                            width=140,
                            alignment=ft.Alignment(0, 0),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.hero_bg,
                border_radius=22,
                padding=20,
            )
        else:
            next_hero = ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("YOUR DIGITAL MEDICINE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                                ft.Text("All Doses Completed!", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text("You are fully consistent today. Great adherence!", size=12, color=ft.Colors.WHITE70),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Text("✨", size=40),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.hero_bg,
                border_radius=22,
                padding=20,
            )

        # Medication Product Cards Wrap (matching Screen 2 in Image 2)
        cards_wrap = ft.Row(
            wrap=True,
            spacing=16,
            run_spacing=16,
        )

        display_meds = meds
        if med_filter["value"] == "low":
            display_meds = low_stock_meds

        if search_query["value"]:
            q = search_query["value"].lower()
            display_meds = [m for m in display_meds if q in m[2].lower() or (m[8] and q in m[8].lower())]

        for med in display_meds:
            cards_wrap.controls.append(build_medication_card(med, theme))

        # Today's Timeline Checklist Column
        timeline_column = ft.Column(spacing=8)
        taken_slots_count = 0
        for t_str, med in today_slots:
            is_taken = any(
                h[0] == med[2] and h[1] == "taken" and str(h[2]).startswith(today_str)
                for h in history
            )
            if is_taken:
                taken_slots_count += 1
                badge = ft.Container(
                    content=ft.Text("✓ Taken", size=11, color=theme.tag_text, weight=ft.FontWeight.BOLD),
                    bgcolor=theme.tag_bg,
                    border_radius=12,
                    padding=ft.Padding(8, 4, 8, 4),
                )
            else:
                badge = ft.OutlinedButton(
                    "Take dose",
                    height=28,
                    border_radius=14,
                    on_click=lambda e, mid=med[0]: mark_dose(mid, "taken"),
                )

            entry_row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(t_str, size=13, weight=ft.FontWeight.BOLD, color=theme.primary, width=50),
                        ft.Column(
                            [
                                ft.Text(med[2], size=13, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Text(f"{med[3]} · {med[8] or 'Myself'}", size=11, color=theme.text_muted),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                        badge,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border_radius=14,
                padding=ft.Padding(12, 8, 12, 8),
                border=ft.Border.all(1, theme.border),
            )
            timeline_column.controls.append(entry_row)

        # 7-day adherence stats card
        pct, taken_count, total_count = calculate_adherence_stats(history)
        adherence_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Adherence Rate", size=11, color=theme.text_muted),
                    ft.Text(f"{pct}%", size=24, weight=ft.FontWeight.BOLD, color=theme.primary),
                    ft.Text(f"{taken_count} of {total_count} doses taken this week", size=11, color=theme.text_secondary),
                ],
                spacing=2,
            ),
            bgcolor=theme.surface,
            border_radius=18,
            padding=16,
            border=ft.Border.all(1, theme.border),
        )

        return ft.Column(
            [
                next_hero,
                banner_container,
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("Your Medications", size=18, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                        ft.Text(f"Showing {len(display_meds)} active prescriptions", size=12, color=theme.text_muted),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                cards_wrap if display_meds else ft.Container(
                                    content=ft.Text("No medications match your filter.", size=12, color=theme.text_muted),
                                    padding=20,
                                ),
                            ],
                            expand=3,
                            spacing=12,
                        ),
                        ft.Column(
                            [
                                ft.Text("Today's Schedule", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                timeline_column if today_slots else ft.Text("No doses scheduled for today.", size=12, color=theme.text_muted),
                                ft.Container(height=8),
                                adherence_card,
                            ],
                            expand=2,
                            spacing=10,
                        ),
                    ],
                    spacing=20,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        )

    # 2. VIEW BUILDER: MEDS (Dedicated Medications Cards Grid Workspace)
    def render_meds_view(meds, theme):
        cards_wrap = ft.Row(
            wrap=True,
            spacing=16,
            run_spacing=16,
        )
        for med in meds:
            cards_wrap.controls.append(build_medication_card(med, theme))

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Your Medications Portfolio", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Text("Manage prescriptions, update dosages, monitor stock supplies, and organize schedules.", size=12, color=theme.text_muted),
                            ],
                            spacing=2,
                        ),
                        ft.Button(
                            "+ Add Medication",
                            icon=ft.Icons.ADD,
                            bgcolor=theme.primary,
                            color=ft.Colors.WHITE,
                            height=38,
                            border_radius=19,
                            on_click=handle_open_add_drawer,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=theme.border),
                cards_wrap if meds else ft.Text("No medications added yet. Click '+ Add Medication' above to get started.", size=13, color=theme.text_muted),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # 3. VIEW BUILDER: SCHEDULE (Timeline & Slot checklist)
    def render_schedule_view(meds, history, today_slots, theme):
        today_str = date.today().isoformat()
        slots_column = ft.Column(spacing=12)

        for t_str, med in today_slots:
            is_taken = any(
                h[0] == med[2] and h[1] == "taken" and str(h[2]).startswith(today_str)
                for h in history
            )
            action_btn = (
                ft.Container(
                    content=ft.Text("✓ Logged Taken", size=12, color=theme.tag_text, weight=ft.FontWeight.BOLD),
                    bgcolor=theme.tag_bg,
                    border_radius=10,
                    padding=ft.Padding(10, 6, 10, 6),
                )
                if is_taken
                else ft.Button(
                    "Mark Taken",
                    icon=ft.Icons.CHECK,
                    bgcolor=theme.primary,
                    color=ft.Colors.WHITE,
                    height=34,
                    border_radius=17,
                    on_click=lambda e, mid=med[0]: mark_dose(mid, "taken"),
                )
            )

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(t_str, size=16, weight=ft.FontWeight.BOLD, color=theme.primary, width=65),
                        ft.Column(
                            [
                                ft.Text(f"{med[2]} · {med[3]}", size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Text(f"For: {med[8] or 'Myself'}  ·  {med[5]}", size=12, color=theme.text_secondary),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        action_btn,
                        ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_color=theme.primary, tooltip="Edit", on_click=lambda e, m=med: handle_edit(m)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_500, tooltip="Delete", on_click=lambda e, mid=med[0], mname=med[2]: handle_delete(mid, mname)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border),
                border_radius=18,
                padding=14,
            )
            slots_column.controls.append(row)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Daily Schedule Checklist", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("Tick off daily doses as you take or administer them.", size=12, color=theme.text_muted)]),
                        ft.Button("+ Add Schedule Slot", icon=ft.Icons.ADD, bgcolor=theme.primary, color=ft.Colors.WHITE, height=38, border_radius=19, on_click=handle_open_add_drawer),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=theme.border),
                slots_column if today_slots else ft.Text("No schedule slots found.", size=13, color=theme.text_muted),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # 4. VIEW BUILDER: HISTORY & CSV EXPORT
    def render_history_view(history, theme):
        history_rows = ft.Column(spacing=6)
        pct, taken_count, total_count = calculate_adherence_stats(history)

        for record in history:
            med_name = record[0]
            status = record[1]
            taken_at = record[2]
            sched_slot = record[3] if len(record) > 3 and record[3] else "—"

            is_taken = status == "taken"
            badge = ft.Container(
                content=ft.Text("TAKEN" if is_taken else "SKIPPED", size=10, weight=ft.FontWeight.BOLD, color=theme.tag_text if is_taken else theme.text_muted),
                bgcolor=theme.tag_bg if is_taken else theme.surface_alt,
                border_radius=6,
                padding=ft.Padding(8, 3, 8, 3),
            )

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(str(taken_at), size=12, color=theme.text_muted, width=150),
                        ft.Text(med_name, size=13, weight=ft.FontWeight.BOLD, color=theme.text_primary, expand=True),
                        ft.Text(f"Slot: {sched_slot}", size=12, color=theme.text_muted, width=100),
                        badge,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border_subtle),
                border_radius=12,
                padding=ft.Padding(12, 10, 12, 10),
            )
            history_rows.controls.append(row)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Dose History & Compliance", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("Complete clinical audit trail of all logged and skipped doses.", size=12, color=theme.text_muted)]),
                        ft.Button("Export Doctor-Ready CSV", icon=ft.Icons.DOWNLOAD, bgcolor=theme.primary, color=ft.Colors.WHITE, height=38, border_radius=19, on_click=handle_export_csv),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    [
                        ft.Container(content=ft.Column([ft.Text("Adherence Rate", size=11, color=theme.text_muted), ft.Text(f"{pct}%", size=24, weight=ft.FontWeight.BOLD, color=theme.primary)]), bgcolor=theme.surface, border_radius=16, padding=16, border=ft.Border.all(1, theme.border), expand=1),
                        ft.Container(content=ft.Column([ft.Text("Doses Taken", size=11, color=theme.text_muted), ft.Text(f"{taken_count}", size=24, weight=ft.FontWeight.BOLD, color=theme.primary)]), bgcolor=theme.surface, border_radius=16, padding=16, border=ft.Border.all(1, theme.border), expand=1),
                        ft.Container(content=ft.Column([ft.Text("Total Logged", size=11, color=theme.text_muted), ft.Text(f"{total_count}", size=24, weight=ft.FontWeight.BOLD, color=theme.text_primary)]), bgcolor=theme.surface, border_radius=16, padding=16, border=ft.Border.all(1, theme.border), expand=1),
                    ],
                    spacing=12,
                ),
                ft.Divider(height=1, color=theme.border),
                history_rows if history else ft.Text("No doses logged in history yet.", size=13, color=theme.text_muted),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # 5. VIEW BUILDER: SETTINGS & ACCESSIBILITY PREFERENCES
    def render_settings_view(theme):
        is_dark = theme.is_dark
        rec_list = get_care_recipients_for_caregiver(user_id) if user_id else []

        new_rec_name = ft.TextField(label="Recipient Name", hint_text="e.g. Mother", expand=2)
        new_rec_rel = ft.TextField(label="Relationship", hint_text="e.g. Parent", expand=2)
        add_rec_msg = ft.Text(value="", size=11)

        def add_rec(e):
            n = new_rec_name.value.strip() if new_rec_name.value else ""
            r = new_rec_rel.value.strip() if new_rec_rel.value else ""
            if not n or not r:
                add_rec_msg.value = "Enter both name and relationship."
                add_rec_msg.color = ft.Colors.RED_500
                page.update()
                return
            insert_care_recipient(user_id, n, r)
            new_rec_name.value = ""
            new_rec_rel.value = ""
            add_rec_msg.value = f"Added {n} as a care recipient."
            add_rec_msg.color = theme.primary
            refresh_all()
            page.update()

        recipients_column = ft.Column(spacing=8)
        for recipient in rec_list:
            rid, _, rname, rrel = recipient[0], recipient[1], recipient[2], recipient[3]
            r_card = ft.Container(
                content=ft.Row(
                    [
                        ft.Text("👤", size=20),
                        ft.Column([ft.Text(rname, size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text(rrel, size=11, color=theme.text_muted)], spacing=1, expand=True),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_500, tooltip="Delete recipient", on_click=lambda e, r_id=rid, r_nm=rname: show_delete_recipient_dialog(page, r_id, r_nm, on_deleted=refresh_all)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border),
                border_radius=14,
                padding=12,
            )
            recipients_column.controls.append(r_card)

        def trigger_backup(e):
            ok, p = create_database_backup("manual_settings")
            global_snack_text.value = f"✓ Backup created: {os.path.basename(p)}" if ok else f"Backup error: {p}"
            page.update()

        def trigger_vacuum(e):
            ok, m = vacuum_database()
            global_snack_text.value = "✓ Database optimized and vacuumed." if ok else f"Vacuum error: {m}"
            page.update()

        theme_switch = ft.Switch(
            label="Dark mode (Low-glare forest slate for vision comfort)",
            value=is_dark,
            on_change=toggle_theme_mode,
            active_color=theme.primary,
        )

        return ft.Column(
            [
                ft.Column([ft.Text("Settings & Accessibility Preferences", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("Customize appearance for vision comfort and manage dependents.", size=12, color=theme.text_muted)]),
                ft.Divider(height=1, color=theme.border),
                ft.Text("Vision & Accessibility", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                ft.Container(
                    content=ft.Column(
                        [
                            theme_switch,
                            ft.Text("Switches the color scheme to anti-glare dark forest moss or warm sage neutral to prevent glare and eye fatigue.", size=11, color=theme.text_muted),
                        ],
                        spacing=6,
                    ),
                    bgcolor=theme.surface,
                    border=ft.Border.all(1, theme.border),
                    border_radius=18,
                    padding=16,
                ),
                ft.Divider(height=1, color=theme.border),
                ft.Text("People You Care For", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([new_rec_name, new_rec_rel, ft.Button("Add Person", icon=ft.Icons.ADD, bgcolor=theme.primary, color=ft.Colors.WHITE, on_click=add_rec)]),
                            add_rec_msg,
                        ],
                        spacing=8,
                    ),
                    bgcolor=theme.surface,
                    border=ft.Border.all(1, theme.border),
                    border_radius=18,
                    padding=16,
                ),
                recipients_column if rec_list else ft.Text("No care recipients added yet.", size=12, color=theme.text_muted),
                ft.Divider(height=1, color=theme.border),
                ft.Text("Database Maintenance", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                ft.Row(
                    [
                        ft.Button("Create Backup Snapshot", icon=ft.Icons.BACKUP, on_click=trigger_backup),
                        ft.Button("Vacuum & Optimize DB", icon=ft.Icons.AUTO_FIX_HIGH, on_click=trigger_vacuum),
                    ],
                    spacing=10,
                ),
                global_snack_text,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # Category Filter Pills Builder (Matching Image 2 Screen 2: All Medicines, Daily Nutrition, Vitamins...)
    def build_category_pills(meds, low_stock_meds, today_slots, theme):
        cur = active_nav["current"]

        def make_pill(key, label, count=None):
            is_active = (cur == key) or (key == "low" and med_filter["value"] == "low" and cur == "today")
            title = f"{label} ({count})" if count is not None else label
            return ft.Container(
                content=ft.Text(
                    title,
                    size=12,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                    color=theme.pill_active_text if is_active else theme.pill_inactive_text,
                ),
                bgcolor=theme.pill_active_bg if is_active else theme.pill_inactive_bg,
                border=None if is_active else ft.Border.all(1, theme.border),
                border_radius=20,
                padding=ft.Padding(16, 8, 16, 8),
                on_click=lambda e, k=key: handle_pill_click(k),
            )

        def handle_pill_click(key):
            if key == "low":
                active_nav["current"] = "today"
                med_filter["value"] = "low"
            elif key == "all":
                active_nav["current"] = "today"
                med_filter["value"] = "all"
            else:
                active_nav["current"] = key
                med_filter["value"] = "all"
            refresh_all()
            page.update()

        return ft.Row(
            [
                make_pill("all", "All Medicines", len(meds)),
                make_pill("schedule", "Daily Schedule", len(today_slots)),
                make_pill("low", "Low Supply", len(low_stock_meds)),
                make_pill("meds", "Prescriptions", len(meds)),
                make_pill("history", "Dose History"),
                make_pill("settings", "Settings & Vision"),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
        )

    # Re-renders entire dashboard with the active theme
    def refresh_all():
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        theme = AppTheme(is_dark)

        meds = get_medications_for_user(user_id)
        med_list_cache["meds"] = meds
        history = get_dose_history_for_user(user_id)
        low_stock_meds = [m for m in meds if m[9] is not None and m[9] <= LOW_STOCK_THRESHOLD]

        # Evaluate today's schedule slots
        today_slots = []
        for med in meds:
            med_id = med[0]
            schedules = get_schedules_for_medication(med_id)
            times = [s[2] for s in schedules] if schedules else []
            if not times and med[4]:
                times = [t.strip() for t in re.split(r"[,;]+", med[4]) if t.strip()]
            for t in times:
                today_slots.append((t, med))
        today_slots.sort(key=lambda x: x[0])

        now_time_str = datetime.now().strftime("%H:%M")
        next_candidate = None
        for t_str, med in today_slots:
            if next_candidate is None and t_str >= now_time_str:
                next_candidate = (t_str, med)

        # Refill Banner in Today tab
        if low_stock_meds and not banner_dismissed["value"]:
            first_low = low_stock_meds[0]
            banner_container.visible = True
            banner_container.content = ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Text("⚠️", size=16),
                                ft.Text(
                                    f"{first_low[2]} has only {first_low[9]} doses remaining. Refill now to stay protected.",
                                    size=12,
                                    weight=ft.FontWeight.W_500,
                                    color=theme.banner_text,
                                ),
                            ],
                            spacing=8,
                            expand=True,
                        ),
                        ft.Button(
                            "Log refill",
                            bgcolor=theme.banner_btn,
                            color=ft.Colors.WHITE,
                            height=30,
                            on_click=lambda e, m=first_low: handle_refill(m[0], m[2], m[9]),
                        ),
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            icon_size=16,
                            icon_color=theme.banner_text,
                            on_click=lambda e: (banner_dismissed.update({"value": True}), refresh_all(), page.update()),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor=theme.banner_bg,
                border=ft.Border.all(1, theme.banner_border),
                border_radius=14,
                padding=ft.Padding(12, 8, 12, 8),
            )
        else:
            banner_container.visible = False

        # Category pills bar
        category_pills_container.content = build_category_pills(meds, low_stock_meds, today_slots, theme)

        # Switch workspace view
        cur = active_nav["current"]
        if cur == "today":
            main_workspace_container.content = render_today_view(meds, history, low_stock_meds, today_slots, next_candidate, theme)
        elif cur == "meds":
            main_workspace_container.content = render_meds_view(meds, theme)
        elif cur == "schedule":
            main_workspace_container.content = render_schedule_view(meds, history, today_slots, theme)
        elif cur == "history":
            main_workspace_container.content = render_history_view(history, theme)
        elif cur == "settings":
            main_workspace_container.content = render_settings_view(theme)

        # Update styling
        header_bar.bgcolor = theme.surface
        header_bar.border = ft.Border(bottom=ft.BorderSide(1, theme.border))
        dock_container.bgcolor = theme.surface
        dock_container.border = ft.Border.all(1, theme.border)
        root_view.bgcolor = theme.bg

        theme_mode_btn.icon = ft.Icons.LIGHT_MODE_OUTLINED if is_dark else ft.Icons.DARK_MODE_OUTLINED
        theme_mode_btn.tooltip = "Switch to Light mode" if is_dark else "Switch to Dark mode (for eye comfort)"
        theme_mode_btn.icon_color = theme.primary if is_dark else theme.text_secondary
        add_med_btn.bgcolor = theme.primary
        add_med_btn.color = ft.Colors.WHITE

    # Top Header Bar
    def handle_search_change(e):
        search_query["value"] = e.control.value
        refresh_all()
        page.update()

    search_field = ft.TextField(
        hint_text="Search medicines, doses, recipients...",
        prefix_icon=ft.Icons.SEARCH,
        width=300,
        height=38,
        text_size=12,
        content_padding=ft.Padding(8, 0, 8, 0),
        border_radius=19,
        border_color="#DFE5DC",
        on_change=handle_search_change,
    )

    theme_mode_btn = ft.IconButton(
        icon=ft.Icons.DARK_MODE_OUTLINED,
        tooltip="Toggle Dark / Light mode (for eye comfort)",
        on_click=toggle_theme_mode,
    )

    add_med_btn = ft.Button(
        "+ Add medication",
        icon=ft.Icons.ADD,
        bgcolor="#52734D",
        color=ft.Colors.WHITE,
        height=38,
        border_radius=19,
        on_click=handle_open_add_drawer,
    )

    header_bar = ft.Container(
        content=ft.Row(
            [
                # Left Brand & User Greeting
                ft.Row(
                    [
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD, color="#2E4A28"),
                            bgcolor="#E5EDE2",
                            radius=18,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("meditrack", size=18, weight=ft.FontWeight.BOLD, color="#1B4332"),
                                        ft.Container(width=6, height=6, border_radius=3, bgcolor="#52734D"),
                                    ],
                                    spacing=4,
                                ),
                                ft.Text("Your Daily Health Partner", size=11, color="#687B67", weight=ft.FontWeight.W_500),
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=10,
                ),
                # Center Search Field
                search_field,
                # Right Actions
                ft.Row(
                    [
                        theme_mode_btn,
                        add_med_btn,
                        ft.IconButton(ft.Icons.NOTIFICATIONS_OUTLINED, icon_color=ft.Colors.GREY_600),
                        ft.IconButton(ft.Icons.LOGOUT, icon_size=18, tooltip="Log out", on_click=on_logout),
                    ],
                    spacing=6,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(24, 12, 24, 12),
    )

    def handle_dock_refill(e):
        meds = med_list_cache["meds"]
        lows = [m for m in meds if m[9] is not None and m[9] <= LOW_STOCK_THRESHOLD]
        target = lows[0] if lows else (meds[0] if meds else None)
        if target:
            handle_refill(target[0], target[2], target[9])
        else:
            handle_open_add_drawer()

    # Floating Bottom Action Dock (Matching Screen 2 in Image 2: [ 🛒 ] [ Go to Cart > ])
    dock_container = ft.Container(
        content=ft.Row(
            [
                ft.Button(
                    "Log Refill",
                    icon=ft.Icons.SHOPPING_BAG_OUTLINED,
                    bgcolor="#E5EDE2",
                    color="#2E4A28",
                    height=40,
                    border_radius=20,
                    on_click=handle_dock_refill,
                ),
                ft.Button(
                    "+ Add Medication",
                    icon=ft.Icons.ADD,
                    bgcolor="#52734D",
                    color=ft.Colors.WHITE,
                    height=40,
                    border_radius=20,
                    on_click=handle_open_add_drawer,
                ),
                ft.Button(
                    "Export Adherence",
                    icon=ft.Icons.DOWNLOAD,
                    bgcolor="#E5EDE2",
                    color="#2E4A28",
                    height=40,
                    border_radius=20,
                    on_click=handle_export_csv,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        ),
        border_radius=24,
        padding=ft.Padding(16, 8, 16, 8),
        alignment=ft.Alignment(0, 0),
    )

    # Body Content: Category Pills + Main Workspace + Dock
    content_column = ft.Column(
        [
            ft.Container(height=4),
            category_pills_container,
            ft.Container(height=8),
            main_workspace_container,
            ft.Container(height=12),
            ft.Row([dock_container], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=8),
        ],
        expand=True,
        spacing=0,
    )

    root_view = ft.View(
        route="/dashboard",
        controls=[
            header_bar,
            ft.Container(content=content_column, padding=ft.Padding(24, 12, 24, 12), expand=True),
        ],
        padding=0,
    )

    # Initial workspace load
    refresh_all()

    return root_view
