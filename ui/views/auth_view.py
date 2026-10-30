"""
MediTrack Authentication View (Login & Registration)
Supports both mouse click and Enter key (on_submit) form submissions.
"""

import flet as ft
from config import APP_VERSION
from database import insert_user, hash_password, login_user, get_user_by_email

def build_auth_view(page: ft.Page, on_login_success):
    """
    Constructs the registration and login view with Enter-key submission support.
    """
    name_field = ft.TextField(label="Name")
    email_field = ft.TextField(label="Email")
    password_field = ft.TextField(label="Password", password=True)
    register_message = ft.Text(value="")

    def register_clicked(e):
        name = name_field.value.strip() if name_field.value else ""
        email = email_field.value.strip() if email_field.value else ""
        password = password_field.value.strip() if password_field.value else ""

        if not name or not email or not password:
            register_message.value = "Please fill in all fields."
            register_message.color = ft.Colors.RED_500
            page.update()
            return

        hashed = hash_password(password)
        success, result_message = insert_user(name, email, hashed)
        register_message.value = result_message
        register_message.color = ft.Colors.GREEN_700 if success else ft.Colors.RED_500
        if success:
            # Prefill login email
            login_email_field.value = email
            login_password_field.focus()
        page.update()

    # Allow Enter key to submit registration from password field
    password_field.on_submit = register_clicked

    login_email_field = ft.TextField(label="Login Email")
    login_password_field = ft.TextField(label="Login Password", password=True)
    login_message = ft.Text(value="")

    def login_clicked(e):
        email = login_email_field.value.strip() if login_email_field.value else ""
        password = login_password_field.value.strip() if login_password_field.value else ""

        if not email or not password:
            login_message.value = "Please enter email and password."
            login_message.color = ft.Colors.RED_500
            page.update()
            return

        success, result_message = login_user(email, password)
        login_message.value = result_message
        login_message.color = ft.Colors.GREEN_700 if success else ft.Colors.RED_500
        page.update()

        if success:
            user = get_user_by_email(email)
            if user and on_login_success:
                on_login_success(user)

    # Allow Enter key on BOTH email and password fields to trigger instant login
    login_email_field.on_submit = login_clicked
    login_password_field.on_submit = login_clicked

    return ft.View(
        route="/",
        controls=[
            ft.Row(
                [
                    ft.Text("MediTrack", size=28, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Text(f"v{APP_VERSION}", size=12, color=ft.Colors.GREY_500),
                        padding=ft.Padding(top=10, bottom=0, left=4, right=0)
                    )
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
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
