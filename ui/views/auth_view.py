"""
ui/views/auth_view.py
MediTrack Split-Screen Authentication View.
Faithfully reproduces the modern Solara-inspired design:
- Left pane: Crisp white background, clean form fields, Sign in / Sign up mode switch,
  "Remember me" checkbox, full-width forest green button, and Enter-key instant submit.
- Right pane: Deep forest green background, support link, floating health goals hero card,
  "Introducing new features" highlight, and pagination dots.
"""
import flet as ft
from config import APP_VERSION
from database import insert_user, hash_password, login_user, get_user_by_email

def build_auth_view(page: ft.Page, on_login_success):
    """
    Constructs the split-screen authentication view matching the reference design.
    """
    is_signup_mode = {"value": False}

    # Left Pane Form Controls
    name_field = ft.TextField(
        hint_text="e.g. Bernard AMG",
        border_radius=10,
        border_color="#D1D5DB",
        focused_border_color="#1B4332",
        text_size=13,
        content_padding=ft.Padding(14, 12, 14, 12),
    )

    email_field = ft.TextField(
        hint_text="example@gmail.com",
        border_radius=10,
        border_color="#D1D5DB",
        focused_border_color="#1B4332",
        text_size=13,
        content_padding=ft.Padding(14, 12, 14, 12),
    )

    password_field = ft.TextField(
        hint_text="@#*%",
        password=True,
        can_reveal_password=True,
        border_radius=10,
        border_color="#D1D5DB",
        focused_border_color="#1B4332",
        text_size=13,
        content_padding=ft.Padding(14, 12, 14, 12),
    )

    remember_me_check = ft.Checkbox(
        label="Remember me",
        value=True,
        check_color=ft.Colors.WHITE,
        fill_color="#1B4332",
    )

    auth_message = ft.Text(value="", size=12, weight=ft.FontWeight.W_500)

    # Dynamic Containers for Left Pane
    title_text = ft.Text("Sign in", size=30, weight=ft.FontWeight.BOLD, color="#111827")
    mode_prompt_text = ft.Text("Don't have an account?", size=12, color="#6B7280")
    mode_switch_btn = ft.TextButton("Create now")

    submit_btn = ft.Button(
        "Sign in",
        bgcolor="#1B4332",
        color=ft.Colors.WHITE,
        height=44,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        width=400,
    )

    form_fields_column = ft.Column(spacing=12)
    remember_row = ft.Row(
        [
            remember_me_check,
            ft.TextButton(
                "Forgot Password?",
                on_click=lambda e: (setattr(auth_message, "value", "Please contact support@meditrack.app to reset credentials."), setattr(auth_message, "color", "#1B4332"), page.update()),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # Action Handlers
    def handle_submit(e=None):
        auth_message.value = ""
        email = email_field.value.strip() if email_field.value else ""
        password = password_field.value.strip() if password_field.value else ""

        if is_signup_mode["value"]:
            name = name_field.value.strip() if name_field.value else ""
            if not name or not email or not password:
                auth_message.value = "Please fill in your name, email, and password."
                auth_message.color = ft.Colors.RED_600
                page.update()
                return

            hashed = hash_password(password)
            success, result_message = insert_user(name, email, hashed)
            auth_message.value = result_message
            auth_message.color = ft.Colors.GREEN_700 if success else ft.Colors.RED_600
            if success:
                # Switch back to login with prefilled email
                toggle_mode()
                email_field.value = email
                password_field.value = ""
                auth_message.value = "Account created successfully! Please sign in."
                auth_message.color = ft.Colors.GREEN_700
            page.update()
        else:
            if not email or not password:
                auth_message.value = "Please enter both email and password."
                auth_message.color = ft.Colors.RED_600
                page.update()
                return

            success, result_message = login_user(email, password)
            auth_message.value = result_message
            auth_message.color = ft.Colors.GREEN_700 if success else ft.Colors.RED_600
            page.update()

            if success:
                user = get_user_by_email(email)
                if user and on_login_success:
                    on_login_success(user)

    # Enter key submits instantly from all fields
    name_field.on_submit = handle_submit
    email_field.on_submit = handle_submit
    password_field.on_submit = handle_submit
    submit_btn.on_click = handle_submit

    def toggle_mode(e=None):
        is_signup_mode["value"] = not is_signup_mode["value"]
        auth_message.value = ""
        render_left_form()
        page.update()

    mode_switch_btn.on_click = toggle_mode

    def render_left_form():
        form_fields_column.controls.clear()
        if is_signup_mode["value"]:
            title_text.value = "Create account"
            mode_prompt_text.value = "Already have an account?"
            mode_switch_btn.text = "Sign in"
            submit_btn.text = "Create account"
            remember_row.visible = False

            form_fields_column.controls.extend(
                [
                    ft.Text("Full Name", size=12, weight=ft.FontWeight.W_600, color="#374151"),
                    name_field,
                    ft.Text("E-mail", size=12, weight=ft.FontWeight.W_600, color="#374151"),
                    email_field,
                    ft.Text("Password", size=12, weight=ft.FontWeight.W_600, color="#374151"),
                    password_field,
                ]
            )
        else:
            title_text.value = "Sign in"
            mode_prompt_text.value = "Don't have an account?"
            mode_switch_btn.text = "Create now"
            submit_btn.text = "Sign in"
            remember_row.visible = True

            form_fields_column.controls.extend(
                [
                    ft.Text("E-mail", size=12, weight=ft.FontWeight.W_600, color="#374151"),
                    email_field,
                    ft.Text("Password", size=12, weight=ft.FontWeight.W_600, color="#374151"),
                    password_field,
                ]
            )

    render_left_form()

    # Demo Quick Login
    def demo_quick_login(e):
        email_field.value = "bernard@example.com"
        password_field.value = "Password123!"
        handle_submit()

    # Left Pane Construction (Crisp White #FFFFFF)
    left_pane = ft.Container(
        content=ft.Column(
            [
                # Top Brand Logo
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SPA_ROUNDED, color="#1B4332", size=26),
                        ft.Text("meditrack", size=22, weight=ft.FontWeight.BOLD, color="#1B4332"),
                    ],
                    spacing=8,
                ),
                ft.Container(height=16),
                title_text,
                ft.Row([mode_prompt_text, mode_switch_btn], spacing=4),
                ft.Container(height=8),
                form_fields_column,
                remember_row,
                ft.Container(height=4),
                submit_btn,
                auth_message,
                ft.Container(height=10),
                # OR Divider
                ft.Row(
                    [
                        ft.Divider(expand=True, color="#E5E7EB"),
                        ft.Text("or", size=11, color="#9CA3AF"),
                        ft.Divider(expand=True, color="#E5E7EB"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                # Google button
                ft.OutlinedButton(
                    content=ft.Row(
                        [
                            ft.Text("G", size=16, weight=ft.FontWeight.BOLD, color="#EA4335"),
                            ft.Text("Continue with Google", size=12, weight=ft.FontWeight.W_500, color="#374151"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    height=42,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    width=400,
                    on_click=lambda e: (setattr(auth_message, "value", "Google OAuth SSO connects automatically in production."), setattr(auth_message, "color", "#1B4332"), page.update()),
                ),
                # Quick Demo / Caregiver login button
                ft.OutlinedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.PERSON_OUTLINED, size=18, color="#1B4332"),
                            ft.Text("Quick Sign In (Demo Account)", size=12, weight=ft.FontWeight.W_500, color="#374151"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    height=42,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    width=400,
                    on_click=demo_quick_login,
                ),
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor="#FFFFFF",
        expand=1,
        padding=ft.Padding(50, 40, 50, 40),
    )

    # Right Pane Construction (Deep Forest Green #133827)
    support_dialog = ft.AlertDialog(
        title=ft.Text("MediTrack Care Support"),
        content=ft.Text("Need help with medication schedules or patient management?\n\nContact our clinical support line at support@meditrack.app or visit documentation."),
        actions=[ft.TextButton("Close", on_click=lambda e: (page.pop_dialog(), page.update()))],
    )

    def show_support(e):
        page.show_dialog(support_dialog)
        page.update()

    right_pane = ft.Container(
        content=ft.Column(
            [
                # Support header link
                ft.Row(
                    [
                        ft.TextButton(
                            content=ft.Row([ft.Icon(ft.Icons.HEADSET_MIC_ROUNDED, size=16, color=ft.Colors.WHITE), ft.Text("Support", color=ft.Colors.WHITE, size=12)], spacing=6),
                            on_click=show_support,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
                ft.Container(expand=True),
                # Floating Hero Card (Reach health goals faster)
                ft.Container(
                    content=ft.Row(
                        [
                            # Left column of card
                            ft.Column(
                                [
                                    ft.Text("Reach health\ngoals faster", size=20, weight=ft.FontWeight.BOLD, color="#111827"),
                                    ft.Text(
                                        "Automated schedule reminders and real-time inventory alerts keep you and your loved ones on track.",
                                        size=11,
                                        color="#4B5563",
                                    ),
                                    ft.Container(height=4),
                                    ft.Button(
                                        "Learn more",
                                        bgcolor="#1B4332",
                                        color=ft.Colors.WHITE,
                                        height=32,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
                                        on_click=show_support,
                                    ),
                                ],
                                expand=3,
                                spacing=6,
                            ),
                            # Right column of card (CareCard & Stat Badge)
                            ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Text("meditrack", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                ft.Text("CarePass ID", size=8, color=ft.Colors.WHITE_70),
                                                ft.Text("MT-2026-GH", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            ],
                                            spacing=2,
                                        ),
                                        bgcolor="#1B4332",
                                        border_radius=10,
                                        padding=10,
                                        width=120,
                                    ),
                                    ft.Container(
                                        content=ft.Row(
                                            [
                                                ft.Icon(ft.Icons.SHOW_CHART, size=14, color="#1B4332"),
                                                ft.Column([ft.Text("Adherence", size=8, color="#6B7280"), ft.Text("98.4%", size=11, weight=ft.FontWeight.BOLD, color="#111827")], spacing=0),
                                            ],
                                            spacing=4,
                                        ),
                                        bgcolor="#F3F4F6",
                                        border_radius=8,
                                        padding=6,
                                        width=120,
                                    ),
                                ],
                                expand=2,
                                spacing=8,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor="#FFFFFF",
                    border_radius=18,
                    padding=22,
                ),
                ft.Container(height=30),
                # Introducing new features
                ft.Text("Introducing new features", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(
                    "Intelligent schedule algorithms ensure patients and caregivers always administer the right dose on time. Track stock levels, export doctor-ready adherence reports, and manage family dependents with ease.",
                    size=12,
                    color="#D1E2D6",
                ),
                ft.Container(height=24),
                # Pagination dots & vision toggle
                ft.Row(
                    [
                        ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.WHITE_38),
                        ft.Container(width=16, height=6, border_radius=3, bgcolor=ft.Colors.WHITE),
                        ft.Container(width=6, height=6, border_radius=3, bgcolor=ft.Colors.WHITE_38),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
                ft.Container(expand=True),
            ],
            spacing=8,
        ),
        bgcolor="#133827",
        expand=1,
        padding=ft.Padding(45, 30, 45, 30),
    )

    return ft.View(
        route="/",
        controls=[
            ft.Row(
                [left_pane, right_pane],
                expand=True,
                spacing=0,
            )
        ],
        padding=0,
    )
