"""
ui/views/dashboard_view.py
Faithful desktop implementation of the MediTrack health-tech design.
Features:
- White, Light Blue, and Light Pink palette
- Accessible Dark Mode toggle for users with vision issues, eye strain, or photophobia
- Interactive left navigation rail: Today, Meds, Schedule, History, Settings
- Full CRUD operations:
    * Medications: Add, Read, Update/Edit (with pre-filled drawer), Delete (with confirmation modal)
    * Quick Refill modal dialog
    * Care Recipients: Add, Edit, Delete (with confirmation modal)
- Next Dose Hero Card, Today's doses timeline, Inventory table with supply progress
- Dose History log, clinical adherence stats, and Doctor-Ready CSV export
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
    Constructs the desktop dashboard with White/Light Blue/Light Pink palette and Dark/Light mode toggle.
    """
    user_id = current_user["id"]
    user_name = current_user.get("name") or "User"
    initials = "".join([part[0].upper() for part in user_name.split()[:2]]) or "U"

    # View & Navigation state
    active_nav = {"current": "today"}  # 'today', 'meds', 'schedule', 'history', 'settings'
    med_filter = {"value": "all"}       # 'all' or 'low'
    search_query = {"value": ""}
    banner_dismissed = {"value": False}

    # Dynamic containers
    main_workspace_container = ft.Container(expand=True)
    banner_container = ft.Container()
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
            global_snack_text.color = theme.blue_primary
        else:
            global_snack_text.value = f"Export failed: {msg}"
            global_snack_text.color = ft.Colors.RED_600
        page.update()

    # 1. VIEW BUILDER: TODAY (3-Column Dashboard)
    def render_today_view(meds, history, low_stock_meds, today_slots, next_candidate, theme):
        is_dark = theme.is_dark
        today_str = date.today().isoformat()

        # Build NEXT DOSE Hero Card (Ocean Sky Blue with Soft Pink accents)
        if next_candidate:
            next_time, next_med = next_candidate
            next_hero = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("NEXT DOSE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                                ft.Container(
                                    content=ft.Text("Scheduled", size=10, weight=ft.FontWeight.BOLD, color=theme.pink_pill_text if not is_dark else ft.Colors.WHITE),
                                    bgcolor=theme.pink_pill_bg if not is_dark else theme.pink_primary,
                                    border_radius=6,
                                    padding=ft.Padding(6, 2, 6, 2),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(next_med[2], size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text(f"{next_med[3]}  ·  {next_med[8] or 'Myself'}", size=12, color=ft.Colors.WHITE70),
                        ft.Container(
                            content=ft.Row([ft.Text("🕒", size=11), ft.Text(f"{next_time}", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], spacing=4),
                            bgcolor=ft.Colors.BLACK12 if not is_dark else ft.Colors.WHITE10,
                            border_radius=12,
                            padding=ft.Padding(8, 3, 8, 3),
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Take now",
                                    bgcolor=ft.Colors.WHITE,
                                    color=theme.blue_primary if not is_dark else "#0B1120",
                                    expand=1,
                                    on_click=lambda e, mid=next_med[0]: mark_dose(mid, "taken"),
                                ),
                                ft.OutlinedButton(
                                    "Snooze 10 min",
                                    expand=1,
                                    on_click=lambda e: (page.show_snack_bar(ft.SnackBar(ft.Text("Snoozed 10 mins"))), page.update()) if hasattr(page, "show_snack_bar") else None,
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=6,
                ),
                bgcolor=theme.hero_bg,
                border_radius=16,
                padding=16,
                border=ft.Border.all(1, theme.border) if is_dark else None,
            )
        elif today_slots:
            next_hero = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("NEXT DOSE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                        ft.Text("All Doses Done!", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Great job staying consistent today.", size=12, color=ft.Colors.WHITE70),
                    ],
                    spacing=6,
                ),
                bgcolor=theme.hero_bg,
                border_radius=16,
                padding=16,
            )
        else:
            next_hero = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("NEXT DOSE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                        ft.Text("No medications scheduled", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Click '+ Add medication' to begin.", size=11, color=ft.Colors.WHITE70),
                    ],
                    spacing=4,
                ),
                bgcolor=theme.hero_bg,
                border_radius=16,
                padding=16,
            )

        # Today's doses timeline
        today_doses_column = ft.Column(spacing=10)
        taken_slots_count = 0
        for t_str, med in today_slots:
            is_taken = any(
                h[0] == med[2] and h[1] == "taken" and str(h[2]).startswith(today_str)
                for h in history
            )
            if is_taken:
                taken_slots_count += 1
                badge = ft.Container(
                    content=ft.Text("✓ Taken", size=11, color=theme.blue_pill_text, weight=ft.FontWeight.BOLD),
                    bgcolor=theme.blue_pill_bg,
                    border_radius=8,
                    padding=ft.Padding(8, 4, 8, 4),
                )
            else:
                badge = ft.OutlinedButton(
                    "Mark taken",
                    height=28,
                    on_click=lambda e, mid=med[0]: mark_dose(mid, "taken"),
                )

            entry_row = ft.Row(
                [
                    ft.Text(t_str, size=12, weight=ft.FontWeight.BOLD, color=theme.blue_primary, width=45),
                    ft.Column(
                        [
                            ft.Text(med[2], size=13, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                            ft.Text(f"{med[3]}", size=11, color=theme.text_muted),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    badge,
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=15, icon_color=theme.blue_primary, tooltip="Edit", on_click=lambda e, m=med: handle_edit(m)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            today_doses_column.controls.append(entry_row)

        col1 = ft.Container(
            content=ft.Column(
                [
                    next_hero,
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text("Today's doses", size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                        ft.Text(f"{taken_slots_count} of {len(today_slots)} taken", size=12, color=theme.text_muted),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Divider(height=1, color=theme.border),
                                today_doses_column if today_slots else ft.Text("No doses scheduled for today.", size=12, color=theme.text_muted),
                            ],
                            spacing=10,
                        ),
                        bgcolor=theme.surface,
                        border=ft.Border.all(1, theme.border),
                        border_radius=16,
                        padding=16,
                    ),
                ],
                spacing=14,
            ),
            width=310,
        )

        # Column 2: Medications Table (White / Light Blue / Light Pink harmony)
        med_rows = ft.Column(spacing=6)
        filtered_meds = meds
        if med_filter["value"] == "low":
            filtered_meds = low_stock_meds

        q = search_query["value"].lower().strip()
        if q:
            filtered_meds = [m for m in filtered_meds if q in m[2].lower() or q in (m[3] or "").lower()]

        for i, med in enumerate(filtered_meds):
            mid = med[0]
            mname = med[2]
            mdose = med[3]
            mtimes = med[4]
            mfreq = med[5] or "Daily"
            mqty = med[9]
            initial = mname[0].upper() if mname else "M"
            is_low = mqty is not None and mqty <= LOW_STOCK_THRESHOLD

            # Alternate between Light Blue and Light Pink avatar circles
            use_pink_avatar = i % 2 == 1
            av_bg = theme.pink_pill_bg if use_pink_avatar else theme.blue_pill_bg
            av_color = theme.pink_pill_text if use_pink_avatar else theme.blue_pill_text

            supply_text = f"{mqty} left" if mqty is not None else "—"
            supply_color = theme.pink_primary if is_low else theme.text_secondary

            row_container = ft.Container(
                content=ft.Row(
                    [
                        # Avatar + Name
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(initial, size=11, weight=ft.FontWeight.BOLD, color=av_color),
                                    bgcolor=av_bg,
                                    border_radius=8,
                                    width=28,
                                    height=28,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    [
                                        ft.Text(mname, size=12, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                        ft.Text(mdose, size=10, color=theme.text_muted),
                                    ],
                                    spacing=0,
                                ),
                            ],
                            spacing=8,
                            width=135,
                        ),
                        # Schedule
                        ft.Column(
                            [
                                ft.Text(mfreq, size=11, weight=ft.FontWeight.W_500, color=theme.text_secondary),
                                ft.Text(mtimes, size=10, color=theme.text_muted),
                            ],
                            spacing=0,
                            width=110,
                        ),
                        # Supply
                        ft.Container(
                            content=ft.Text(supply_text, size=11, weight=ft.FontWeight.BOLD if is_low else ft.FontWeight.NORMAL, color=supply_color),
                            width=70,
                        ),
                        # Actions: Edit ✏️ (Blue), Refill +🛒 (Pink), Delete 🗑️ (Red)
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.Icons.EDIT_OUTLINED,
                                    icon_size=16,
                                    icon_color=theme.blue_primary,
                                    tooltip="Edit / Update medication",
                                    on_click=lambda e, m=med: handle_edit(m),
                                ),
                                ft.IconButton(
                                    ft.Icons.ADD_SHOPPING_CART_OUTLINED,
                                    icon_size=16,
                                    icon_color=theme.pink_primary,
                                    tooltip="Refill stock",
                                    on_click=lambda e, m=med: handle_refill(m[0], m[2], m[9]),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE_OUTLINE,
                                    icon_size=16,
                                    icon_color=ft.Colors.RED_500,
                                    tooltip="Delete medication",
                                    on_click=lambda e, mid=mid, mname=mname: handle_delete(mid, mname),
                                ),
                            ],
                            spacing=0,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(6, 6, 6, 6),
                border=ft.Border(bottom=ft.BorderSide(1, theme.border_subtle)),
            )
            med_rows.controls.append(row_container)

        col2 = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("My medications", size=15, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.TextButton(
                                                f"All {len(meds)}",
                                                on_click=lambda e: (med_filter.update({"value": "all"}), refresh_all(), page.update()),
                                            ),
                                            ft.TextButton(
                                                f"Low supply {len(low_stock_meds)}",
                                                on_click=lambda e: (med_filter.update({"value": "low"}), refresh_all(), page.update()),
                                            ),
                                        ],
                                        spacing=2,
                                    ),
                                    bgcolor=theme.surface_alt,
                                    border_radius=10,
                                    padding=2,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(height=1, color=theme.border),
                        ft.Row(
                            [
                                ft.Text("MEDICATION", size=10, weight=ft.FontWeight.BOLD, color=theme.text_muted, width=135),
                                ft.Text("SCHEDULE", size=10, weight=ft.FontWeight.BOLD, color=theme.text_muted, width=110),
                                ft.Text("SUPPLY", size=10, weight=ft.FontWeight.BOLD, color=theme.text_muted, width=70),
                                ft.Text("ACTIONS", size=10, weight=ft.FontWeight.BOLD, color=theme.text_muted),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        med_rows if filtered_meds else ft.Text("No medications match this filter.", size=12, color=theme.text_muted),
                        ft.Divider(height=1, color=theme.border),
                        ft.Row(
                            [
                                ft.Text(f"Showing {len(filtered_meds)} of {len(meds)} medications", size=11, color=theme.text_muted),
                                ft.TextButton("+ Add New", icon=ft.Icons.ADD, on_click=handle_open_add_drawer),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=10,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border),
                border_radius=16,
                padding=16,
            ),
            expand=True,
        )

        # Column 3: Quick Add & Adherence Chart
        quick_name = ft.TextField(hint_text="Medication name (e.g. Amlodipine)", height=38, text_size=12, content_padding=ft.Padding(10, 0, 10, 0))
        quick_str = ft.TextField(hint_text="Strength (5 mg)", expand=1, height=38, text_size=12, content_padding=ft.Padding(10, 0, 10, 0))
        quick_tm = ft.TextField(hint_text="First dose (08:00)", expand=1, height=38, text_size=12, content_padding=ft.Padding(10, 0, 10, 0))
        quick_msg = ft.Text(value="", size=11)

        def save_quick(e):
            n = quick_name.value.strip() if quick_name.value else ""
            if not n:
                quick_msg.value = "Enter a medication name."
                quick_msg.color = ft.Colors.RED_500
                page.update()
                return
            s = quick_str.value.strip() if quick_str.value else "Standard"
            t = normalize_time(quick_tm.value.strip() if quick_tm.value else "08:00") or "08:00"
            insert_medication(user_id, n, s, t, "Daily", None, 30, None)
            quick_name.value = ""
            quick_str.value = ""
            quick_tm.value = ""
            quick_msg.value = f"Saved {n}!"
            quick_msg.color = theme.blue_primary
            refresh_all()
            page.update()

        pct, taken_count, total_count = calculate_adherence_stats(history)

        # 7-day bar chart with alternating Light Blue & Soft Pink weekend highlights
        chart_bars = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.END, height=65)
        for i, (day, h) in enumerate([("Wed", 45), ("Thu", 55), ("Fri", 40), ("Sat", 55), ("Sun", 35), ("Mon", 55), ("Tue", 48)]):
            is_weekend = day in ["Sat", "Sun"]
            bar_color = theme.pink_primary if is_weekend else theme.blue_primary
            chart_bars.controls.append(
                ft.Column(
                    [
                        ft.Container(bgcolor=bar_color, width=18, height=h, border_radius=ft.BorderRadius(3, 3, 0, 0)),
                        ft.Text(day, size=9, color=theme.text_muted, weight=ft.FontWeight.BOLD if is_weekend else ft.FontWeight.NORMAL),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                )
            )

        col3 = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Quick add", size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                quick_name,
                                ft.Row([quick_str, quick_tm]),
                                ft.Row(
                                    [
                                        ft.Button("Save", bgcolor=theme.blue_primary, color=ft.Colors.WHITE, expand=1, on_click=save_quick),
                                        ft.OutlinedButton("More options", on_click=handle_open_add_drawer),
                                    ],
                                    spacing=8,
                                ),
                                quick_msg,
                            ],
                            spacing=8,
                        ),
                        bgcolor=theme.surface,
                        border=ft.Border.all(1, theme.border),
                        border_radius=16,
                        padding=16,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row([ft.Text("This week", size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.TextButton("Full history", on_click=lambda e: switch_nav("history"))], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Row([ft.Text(f"{pct}%", size=28, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("doses taken on time", size=11, color=theme.text_muted)], vertical_alignment=ft.CrossAxisAlignment.END, spacing=6),
                                chart_bars,
                                ft.Divider(height=1, color=theme.border),
                                ft.Row(
                                    [
                                        ft.Text("Current streak", size=11, color=theme.text_muted),
                                        ft.Container(
                                            content=ft.Text(f"🔥 {min(7, taken_count)} days", size=11, weight=ft.FontWeight.BOLD, color=theme.pink_pill_text),
                                            bgcolor=theme.pink_pill_bg,
                                            border_radius=8,
                                            padding=ft.Padding(8, 3, 8, 3),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.OutlinedButton("Export Doctor-Ready CSV", icon=ft.Icons.DOWNLOAD, on_click=handle_export_csv),
                            ],
                            spacing=10,
                        ),
                        bgcolor=theme.surface,
                        border=ft.Border.all(1, theme.border),
                        border_radius=16,
                        padding=16,
                    ),
                ],
                spacing=14,
            ),
            width=290,
        )

        today_formatted = date.today().strftime("%A, %d %b")
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(f"Good afternoon, {user_name.split()[0]}", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Text(f"{today_formatted}. Track your schedule and refills.", size=12, color=theme.text_muted),
                            ],
                            spacing=2,
                        ),
                        ft.Row(
                            [
                                ft.Container(content=ft.Text(f"{taken_slots_count} of {len(today_slots)} taken", size=11, weight=ft.FontWeight.W_500, color=theme.blue_pill_text), bgcolor=theme.blue_pill_bg, border_radius=20, padding=ft.Padding(12, 6, 12, 6)),
                                ft.Container(content=ft.Text(f"{len(low_stock_meds)} running low", size=11, weight=ft.FontWeight.BOLD, color=theme.pink_pill_text), bgcolor=theme.pink_pill_bg, border_radius=20, padding=ft.Padding(12, 6, 12, 6)),
                            ],
                            spacing=8,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                banner_container,
                ft.Row([col1, col2, col3], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, spacing=14),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )

    # 2. VIEW BUILDER: MEDS (Dedicated Medications CRUD Workspace)
    def render_meds_view(meds, theme):
        cards_column = ft.Column(spacing=10)
        for i, med in enumerate(meds):
            mid = med[0]
            mname = med[2]
            mdose = med[3]
            mtimes = med[4]
            mfreq = med[5] or "Daily"
            rec_name = med[8] or "Myself"
            mqty = med[9]
            mexp = med[10] or "Not specified"
            is_low = mqty is not None and mqty <= LOW_STOCK_THRESHOLD

            use_pink = i % 2 == 1
            av_bg = theme.pink_pill_bg if use_pink else theme.blue_pill_bg
            av_text = theme.pink_pill_text if use_pink else theme.blue_pill_text

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(mname[0].upper(), size=16, weight=ft.FontWeight.BOLD, color=av_text),
                            bgcolor=av_bg,
                            border_radius=12,
                            width=42,
                            height=42,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            [
                                ft.Row([ft.Text(mname, size=15, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Container(content=ft.Text(f"👤 {rec_name}", size=11, color=theme.blue_pill_text), bgcolor=theme.blue_pill_bg, border_radius=6, padding=ft.Padding(6, 2, 6, 2))], spacing=8),
                                ft.Text(f"Strength: {mdose}  ·  Schedule: {mfreq} at {mtimes}", size=12, color=theme.text_secondary),
                                ft.Text(f"Stock: {mqty if mqty is not None else 'Uncounted'} remaining  ·  Expires: {mexp}", size=11, color=theme.pink_primary if is_low else theme.text_muted),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Row(
                            [
                                ft.Button("Edit", icon=ft.Icons.EDIT_OUTLINED, on_click=lambda e, m=med: handle_edit(m)),
                                ft.Button("Refill", icon=ft.Icons.ADD_SHOPPING_CART_OUTLINED, bgcolor=theme.pink_primary, color=ft.Colors.WHITE, on_click=lambda e, m=med: handle_refill(m[0], m[2], m[9])),
                                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_500, tooltip="Delete", on_click=lambda e, mid=mid, mname=mname: handle_delete(mid, mname)),
                            ],
                            spacing=6,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border),
                border_radius=16,
                padding=16,
            )
            cards_column.controls.append(card)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Medications Management", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("View, update dosage and schedules, or remove prescriptions.", size=12, color=theme.text_muted)]),
                        ft.Button("+ Add Medication", icon=ft.Icons.ADD, bgcolor=theme.blue_primary, color=ft.Colors.WHITE, on_click=handle_open_add_drawer),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=theme.border),
                cards_column if meds else ft.Text("No medications added yet. Click '+ Add Medication' above.", size=13, color=theme.text_muted),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # 3. VIEW BUILDER: SCHEDULE (Timeline & Slot checklist matching Page 3)
    def render_schedule_view(meds, history, today_slots, theme):
        today_str = date.today().isoformat()
        slots_column = ft.Column(spacing=12)

        for t_str, med in today_slots:
            is_taken = any(
                h[0] == med[2] and h[1] == "taken" and str(h[2]).startswith(today_str)
                for h in history
            )
            action_btn = (
                ft.Container(content=ft.Text("✓ Logged Taken", size=12, color=theme.blue_pill_text, weight=ft.FontWeight.BOLD), bgcolor=theme.blue_pill_bg, border_radius=8, padding=ft.Padding(10, 6, 10, 6))
                if is_taken
                else ft.Button("Mark Taken", icon=ft.Icons.CHECK, bgcolor=theme.blue_primary, color=ft.Colors.WHITE, on_click=lambda e, mid=med[0]: mark_dose(mid, "taken"))
            )

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(t_str, size=16, weight=ft.FontWeight.BOLD, color=theme.blue_primary, width=65),
                        ft.Column(
                            [
                                ft.Text(f"{med[2]} · {med[3]}", size=14, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                                ft.Text(f"For: {med[8] or 'Myself'}  ·  {med[5]}", size=12, color=theme.text_secondary),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        action_btn,
                        ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_color=theme.blue_primary, tooltip="Edit", on_click=lambda e, m=med: handle_edit(m)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_500, tooltip="Delete", on_click=lambda e, mid=med[0], mname=med[2]: handle_delete(mid, mname)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=theme.surface,
                border=ft.Border.all(1, theme.border),
                border_radius=14,
                padding=14,
            )
            slots_column.controls.append(row)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Daily Schedule Checklist", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("Tick off daily doses as you take or administer them.", size=12, color=theme.text_muted)]),
                        ft.Button("+ Add Schedule Slot", icon=ft.Icons.ADD, bgcolor=theme.blue_primary, color=ft.Colors.WHITE, on_click=handle_open_add_drawer),
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
                content=ft.Text("TAKEN" if is_taken else "SKIPPED", size=10, weight=ft.FontWeight.BOLD, color=theme.blue_pill_text if is_taken else theme.text_muted),
                bgcolor=theme.blue_pill_bg if is_taken else theme.surface_alt,
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
                border_radius=10,
                padding=ft.Padding(12, 10, 12, 10),
            )
            history_rows.controls.append(row)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Column([ft.Text("Dose History & Compliance", size=22, weight=ft.FontWeight.BOLD, color=theme.text_primary), ft.Text("Complete clinical audit trail of all logged and skipped doses.", size=12, color=theme.text_muted)]),
                        ft.Button("Export Doctor-Ready CSV", icon=ft.Icons.DOWNLOAD, bgcolor=theme.blue_primary, color=ft.Colors.WHITE, on_click=handle_export_csv),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    [
                        ft.Container(content=ft.Column([ft.Text("Adherence Rate", size=11, color=theme.text_muted), ft.Text(f"{pct}%", size=24, weight=ft.FontWeight.BOLD, color=theme.blue_primary)]), bgcolor=theme.surface, border_radius=14, padding=16, border=ft.Border.all(1, theme.border), expand=1),
                        ft.Container(content=ft.Column([ft.Text("Doses Taken", size=11, color=theme.text_muted), ft.Text(f"{taken_count}", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)]), bgcolor=theme.surface, border_radius=14, padding=16, border=ft.Border.all(1, theme.border), expand=1),
                        ft.Container(content=ft.Column([ft.Text("Total Logged", size=11, color=theme.text_muted), ft.Text(f"{total_count}", size=24, weight=ft.FontWeight.BOLD, color=theme.text_primary)]), bgcolor=theme.surface, border_radius=14, padding=16, border=ft.Border.all(1, theme.border), expand=1),
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
            add_rec_msg.color = theme.blue_primary
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
                border_radius=12,
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
            label="Dark mode (High-contrast anti-glare for vision comfort)",
            value=is_dark,
            on_change=toggle_theme_mode,
            active_color=theme.blue_primary,
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
                            ft.Text("Switches the color scheme to high-contrast dark slate or soft light blue/white/pink to prevent glare and eye fatigue.", size=11, color=theme.text_muted),
                        ],
                        spacing=6,
                    ),
                    bgcolor=theme.surface,
                    border=ft.Border.all(1, theme.border),
                    border_radius=14,
                    padding=16,
                ),
                ft.Divider(height=1, color=theme.border),
                ft.Text("People You Care For", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([new_rec_name, new_rec_rel, ft.Button("Add Person", icon=ft.Icons.ADD, bgcolor=theme.pink_primary, color=ft.Colors.WHITE, on_click=add_rec)]),
                            add_rec_msg,
                        ],
                        spacing=8,
                    ),
                    bgcolor=theme.surface,
                    border=ft.Border.all(1, theme.border),
                    border_radius=14,
                    padding=16,
                ),
                recipients_column if rec_list else ft.Text("No care recipients added yet.", size=12, color=theme.text_muted),
                ft.Divider(height=1, color=theme.border),
                ft.Text("Database Maintenance", size=16, weight=ft.FontWeight.BOLD, color=theme.text_primary),
                ft.Row(
                    [
                        ft.Button("Create Backup Snapshot", icon=ft.Icons.BACKUP, on_click=trigger_backup),
                        ft.Button("Optimize Database (VACUUM)", icon=ft.Icons.CLEANING_SERVICES, on_click=trigger_vacuum),
                    ],
                    spacing=12,
                ),
                global_snack_text,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        )

    # Left Navigation Rail buttons
    nav_buttons = {}

    def switch_nav(tab_name):
        active_nav["current"] = tab_name
        refresh_all()
        page.update()

    # Re-renders entire dashboard with the active theme
    def refresh_all():
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        theme = AppTheme(is_dark)

        meds = get_medications_for_user(user_id)
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
                                    f"{first_low[2]} has {first_low[9]} doses of supply left. Log a refill to keep reminders going.",
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
                border_radius=12,
                padding=ft.Padding(12, 8, 12, 8),
            )
        else:
            banner_container.visible = False

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

        # Update Navigation rail styling
        for key, btn in nav_buttons.items():
            is_active = active_nav["current"] == key
            btn.bgcolor = theme.blue_pill_bg if is_active else ft.Colors.TRANSPARENT
            col = btn.content
            col.controls[0].color = theme.blue_primary if is_active else theme.text_muted
            col.controls[1].color = theme.blue_primary if is_active else theme.text_muted
            col.controls[1].weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL

        # Update Header bar styling
        header_bar.bgcolor = theme.surface
        header_bar.border = ft.Border(bottom=ft.BorderSide(1, theme.border))
        nav_rail.bgcolor = theme.surface
        nav_rail.border = ft.Border(right=ft.BorderSide(1, theme.border))
        root_view.bgcolor = theme.bg

        # Update Theme Mode button and Add button styling
        theme_mode_btn.icon = ft.Icons.LIGHT_MODE_OUTLINED if is_dark else ft.Icons.DARK_MODE_OUTLINED
        theme_mode_btn.tooltip = "Switch to Light mode" if is_dark else "Switch to Dark mode (for eye comfort)"
        theme_mode_btn.icon_color = theme.blue_primary if is_dark else theme.text_secondary
        add_med_btn.bgcolor = theme.blue_primary
        add_med_btn.color = ft.Colors.WHITE if not is_dark else "#0B1120"

    def create_nav_btn(key, icon_active, icon_inactive, label):
        btn = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon_inactive, size=18),
                    ft.Text(label, size=9),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            border_radius=10,
            padding=8,
            width=65,
            on_click=lambda e, k=key: switch_nav(k),
        )
        nav_buttons[key] = btn
        return btn

    nav_rail = ft.Container(
        content=ft.Column(
            [
                create_nav_btn("today", ft.Icons.SUNNY, ft.Icons.SUNNY_SNOWING, "Today"),
                create_nav_btn("meds", ft.Icons.MEDICATION, ft.Icons.MEDICATION_OUTLINED, "Meds"),
                create_nav_btn("schedule", ft.Icons.CALENDAR_MONTH, ft.Icons.CALENDAR_MONTH_OUTLINED, "Schedule"),
                create_nav_btn("history", ft.Icons.HISTORY_ROUNDED, ft.Icons.HISTORY_ROUNDED, "History"),
                create_nav_btn("settings", ft.Icons.TUNE, ft.Icons.TUNE_OUTLINED, "Settings"),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(6, 20, 6, 20),
        width=75,
    )

    # Top Header Bar with Theme Toggle Button
    def handle_search_change(e):
        search_query["value"] = e.control.value
        refresh_all()
        page.update()

    search_field = ft.TextField(
        hint_text="Quick find: medication, dose, history",
        prefix_icon=ft.Icons.SEARCH,
        width=320,
        height=38,
        text_size=12,
        content_padding=ft.Padding(8, 0, 8, 0),
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
        bgcolor="#0284C7",
        color=ft.Colors.WHITE,
        on_click=handle_open_add_drawer,
    )

    header_bar = ft.Container(
        content=ft.Row(
            [
                # Brand with Light Blue & Soft Pink accent
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MEDICATION, color=ft.Colors.LIGHT_BLUE_700, size=24),
                        ft.Row(
                            [
                                ft.Text("Meditrack", size=18, weight=ft.FontWeight.BOLD),
                                ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.PINK_400),
                            ],
                            spacing=3,
                        ),
                    ],
                    spacing=6,
                ),
                search_field,
                ft.Row(
                    [
                        # Accessible Dark / Light Mode Toggle Button
                        theme_mode_btn,
                        add_med_btn,
                        ft.IconButton(ft.Icons.NOTIFICATIONS_OUTLINED, icon_color=ft.Colors.GREY_600),
                        ft.Row(
                            [
                                ft.CircleAvatar(
                                    content=ft.Text(initials, size=11, weight=ft.FontWeight.BOLD, color="#9D174D"),
                                    bgcolor="#FCE7F3",
                                    radius=15,
                                ),
                                ft.Text(user_name, size=12, weight=ft.FontWeight.BOLD),
                                ft.IconButton(ft.Icons.LOGOUT, icon_size=16, tooltip="Log out", on_click=on_logout),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(20, 10, 20, 10),
    )

    body_row = ft.Row([nav_rail, ft.Container(content=main_workspace_container, padding=20, expand=True)], expand=True, spacing=0)

    root_view = ft.View(
        route="/dashboard",
        controls=[header_bar, body_row],
        padding=0,
    )

    # Initial workspace load
    refresh_all()

    return root_view
