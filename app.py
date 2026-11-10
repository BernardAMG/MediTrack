"""
app.py - MediTrack Main Application Entry Point
Refactored to Clean Architecture, delegating to ui.views and services.
Faithfully renders the health-tech desktop design from the reference PDF.
"""
import asyncio
import os
import threading
from datetime import datetime, date
import flet as ft
from config import APP_VERSION, logger
from database import (
    prepare_database_location,
    run_all_migrations,
    check_database_integrity,
)
from services.watcher import (
    _parse_single_time,
    normalize_time,
    should_alert,
    send_alert,
    start_watcher,
)
from services.adherence import format_adherence_summary
from ui.views import build_auth_view, build_dashboard_view

def main(page: ft.Page):
    page.title = "MediTrack"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL_800)
    page.window.width = 1180
    page.window.height = 800
    page.window.min_width = 950
    page.window.min_height = 650

    current_user = {"id": None, "name": None, "email": None}
    already_notified_today = set()

    # Start background watcher daemon from services
    watcher_stop_event = threading.Event()
    watcher_thread, _ = start_watcher(
        current_user,
        stop_event=watcher_stop_event,
        already_notified=already_notified_today
    )

    def on_login_success(user):
        current_user["id"] = user[0]
        current_user["name"] = user[1]
        current_user["email"] = user[2]
        asyncio.create_task(page.push_route("/dashboard"))

    def logout_clicked(e):
        current_user["id"] = None
        current_user["name"] = None
        current_user["email"] = None
        asyncio.create_task(page.push_route("/"))

    def route_change(e):
        page.views.clear()

        if page.route == "/":
            page.views.append(build_auth_view(page, on_login_success=on_login_success))
        elif page.route == "/dashboard":
            if current_user["id"] is None:
                asyncio.create_task(page.push_route("/"))
                return

            page.views.append(build_dashboard_view(page, current_user, on_logout=logout_clicked))

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
