"""
ui/theme.py
MediTrack Design System & Accessibility Theme:
- White, Light Blue, and Light Pink palette
- High-contrast Light Mode and low-glare Dark Mode for vision-sensitive users
"""
import flet as ft

class AppTheme:
    def __init__(self, is_dark: bool = False):
        self.is_dark = is_dark

        if is_dark:
            # Dark Mode (Anti-glare, high contrast for vision issues)
            self.bg = "#0B1120"
            self.surface = "#131C31"
            self.surface_alt = "#1E293B"
            self.border = "#2A3A5E"
            self.border_subtle = "#1E293B"

            # Text
            self.text_primary = "#F8FAFC"
            self.text_secondary = "#CBD5E1"
            self.text_muted = "#94A3B8"

            # Accents: Light Blue & Light Pink
            self.blue_primary = "#38BDF8"       # Bright sky blue
            self.blue_hover = "#7DD3FC"
            self.blue_pill_bg = "#0C4A6E"       # Deep blue pill
            self.blue_pill_text = "#BAE6FD"

            self.pink_primary = "#F472B6"       # Soft glowing pink
            self.pink_hover = "#F9A8D4"
            self.pink_pill_bg = "#701A75"       # Deep pink pill
            self.pink_pill_text = "#FDF2F8"

            self.hero_bg = "#162238"
            self.banner_bg = "#422006"
            self.banner_border = "#78350F"
            self.banner_text = "#FEF3C7"
            self.banner_btn = "#D97706"

        else:
            # Light Mode (White, Light Blue, Light Pink)
            self.bg = "#F0F7FF"                 # Soft ice-blue tinted white
            self.surface = "#FFFFFF"            # Crisp white card surface
            self.surface_alt = "#F8FAFC"        # Off-white
            self.border = "#E0F2FE"             # Soft light blue border
            self.border_subtle = "#F1F5F9"

            # Text (WCAG AAA High Contrast)
            self.text_primary = "#0F172A"       # Deep dark slate
            self.text_secondary = "#334155"     # Medium dark slate
            self.text_muted = "#64748B"         # Muted label slate

            # Accents: Light Blue & Light Pink
            self.blue_primary = "#0284C7"       # Sky blue brand primary
            self.blue_hover = "#0369A1"
            self.blue_pill_bg = "#E0F2FE"       # Soft light-blue pill
            self.blue_pill_text = "#0369A1"

            self.pink_primary = "#DB2777"       # Vibrant accessible pink
            self.pink_hover = "#BE185D"
            self.pink_pill_bg = "#FCE7F3"       # Soft light-pink pill
            self.pink_pill_text = "#9D174D"

            self.hero_bg = "#0369A1"            # Ocean sky blue
            self.banner_bg = "#FEF3C7"          # Warm amber
            self.banner_border = "#FDE68A"
            self.banner_text = "#92400E"
            self.banner_btn = "#92400E"
