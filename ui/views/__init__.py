"""
UI Views Package
"""
from ui.views.auth_view import build_auth_view
from ui.views.dashboard_view import build_dashboard_view

__all__ = [
    "build_auth_view",
    "build_dashboard_view",
]
