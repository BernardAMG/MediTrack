"""
ui/components/medication_card.py
Component for rendering individual medication cards with status badges and action buttons.
"""
import flet as ft

def build_medication_card(
    med: tuple,
    on_take,
    on_skip,
    on_refill,
    on_edit,
    on_delete,
) -> ft.Container:
    """
    Renders a styled card for a medication item.
    med tuple schema: (id, user_id, name, dosage, time, frequency, created_at, recipient_id, recipient_name, quantity_remaining, expiry_date)
    """
    med_id = med[0]
    med_name = med[2]
    dosage = med[3]
    time_str = med[4]
    frequency = med[5]
    recipient_name = med[8]
    quantity = med[9]
    expiry_date = med[10]

    if recipient_name:
        recipient_badge = ft.Container(
            content=ft.Text(f"👤 {recipient_name}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_900),
            bgcolor=ft.Colors.BLUE_50,
            border=ft.Border.all(1, ft.Colors.BLUE_200),
            border_radius=6,
            padding=ft.Padding(left=6, right=6, top=1, bottom=1),
        )
    else:
        recipient_badge = ft.Container(
            content=ft.Text("👤 Myself", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
            bgcolor=ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=6,
            padding=ft.Padding(left=6, right=6, top=1, bottom=1),
        )

    take_button = ft.IconButton(
        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
        icon_color=ft.Colors.GREEN_600,
        tooltip="Mark as taken",
        on_click=lambda e: on_take(med_id),
    )
    skip_button = ft.IconButton(
        icon=ft.Icons.CANCEL_OUTLINED,
        icon_color=ft.Colors.GREY_500,
        tooltip="Mark as skipped",
        on_click=lambda e: on_skip(med_id),
    )
    refill_button = ft.IconButton(
        icon=ft.Icons.ADD_SHOPPING_CART_OUTLINED,
        icon_color=ft.Colors.BLUE_600,
        tooltip="Refill stock",
        on_click=lambda e: on_refill(med_id, med_name, quantity),
    )
    edit_button = ft.IconButton(
        icon=ft.Icons.EDIT_OUTLINED,
        icon_color=ft.Colors.GREY_500,
        tooltip="Edit medication",
        on_click=lambda e: on_edit(med),
    )
    delete_button = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        icon_color=ft.Colors.RED_400,
        tooltip="Delete medication",
        on_click=lambda e: on_delete(med_id),
    )

    stock_info = f" · 📦 {quantity} left" if quantity is not None else ""
    expiry_info = f" · ⌛ Exp: {expiry_date}" if expiry_date else ""

    return ft.Container(
        content=ft.Row(
            [
                ft.Text("💊", size=18),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"{med_name} · {dosage}", size=14, weight=ft.FontWeight.W_500),
                                recipient_badge,
                            ],
                            spacing=6,
                            wrap=True,
                        ),
                        ft.Text(f"⏰ {time_str} ({frequency}){stock_info}{expiry_info}", size=12, color=ft.Colors.GREY_600),
                    ],
                    spacing=3,
                    expand=True,
                ),
                take_button,
                skip_button,
                refill_button,
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
