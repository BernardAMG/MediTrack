"""
test_views.py - Headless unit tests for MediTrack Flet views.
Verifies that all views instantiate properly without invalid keyword arguments.
"""
import unittest
import flet as ft
from ui.views.auth_view import build_auth_view
from ui.views.dashboard_view import build_dashboard_view
from database import prepare_database_location, run_all_migrations

class MockPage:
    def __init__(self, is_dark=False):
        self.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        self.route = "/"
        self.views = []

    def update(self):
        pass

    def show_dialog(self, dlg):
        pass

    def pop_dialog(self):
        pass

class TestUIViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_database_location()
        run_all_migrations()

    def test_auth_view_instantiation(self):
        page = MockPage(is_dark=False)
        auth_view = build_auth_view(page, on_login_success=None)
        self.assertIsNotNone(auth_view)
        self.assertEqual(auth_view.route, "/")

    def test_dashboard_view_light_mode(self):
        page = MockPage(is_dark=False)
        user = {"id": 1, "name": "Bernard AMG", "email": "bernard@example.com"}
        dash_view = build_dashboard_view(page, user, on_logout=None)
        self.assertIsNotNone(dash_view)
        self.assertEqual(dash_view.route, "/dashboard")

    def test_dashboard_view_dark_mode(self):
        page = MockPage(is_dark=True)
        user = {"id": 1, "name": "Bernard AMG", "email": "bernard@example.com"}
        dash_view = build_dashboard_view(page, user, on_logout=None)
        self.assertIsNotNone(dash_view)
        self.assertEqual(dash_view.route, "/dashboard")

if __name__ == "__main__":
    unittest.main()
