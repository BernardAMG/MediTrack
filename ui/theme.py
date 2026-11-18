"""
ui/theme.py
MediTrack Design System & Accessibility Theme:
- Forest Green & Warm Sage aesthetic faithful to the user's reference designs
  (Solara-inspired split login & "Your Daily Health Partner" card-based interface)
- High-contrast Light Mode and low-glare Dark Mode for vision-sensitive users
"""
import flet as ft

class AppTheme:
    def __init__(self, is_dark: bool = False):
        self.is_dark = is_dark

        if is_dark:
            # Dark Mode (Anti-glare moss/midnight slate for vision comfort)
            self.bg = "#111C14"
            self.surface = "#18261C"
            self.surface_alt = "#213326"
            self.border = "#2B4232"
            self.border_subtle = "#1E3023"

            # Text
            self.text_primary = "#F0FDF4"
            self.text_secondary = "#CBD5C1"
            self.text_muted = "#8BA391"

            # Sage / Olive / Forest Green Accents
            self.primary = "#7CB377"            # Glowing bright sage
            self.primary_dark = "#133522"
            self.primary_hover = "#95C990"

            self.pill_active_bg = "#7CB377"
            self.pill_active_text = "#111C14"
            self.pill_inactive_bg = "#213326"
            self.pill_inactive_text = "#CBD5C1"

            self.tag_bg = "#1E3825"
            self.tag_text = "#A3DB9F"

            self.hero_bg = "#1B3A25"

            # Backward compatibility aliases
            self.blue_primary = self.primary
            self.blue_hover = self.primary_hover
            self.blue_pill_bg = self.tag_bg
            self.blue_pill_text = self.tag_text

            self.pink_primary = "#8DBE88"
            self.pink_hover = "#A5D6A0"
            self.pink_pill_bg = "#1E3825"
            self.pink_pill_text = "#E2F0DF"

            self.banner_bg = "#38250C"
            self.banner_border = "#633B0A"
            self.banner_text = "#FEF3C7"
            self.banner_btn = "#B45309"

        else:
            # Light Mode (Crisp White cards #FFFFFF, Soft slate background #F8FAFC, Deep Teal #0F5147)
            self.bg = "#F8FAFC"                 # Soft clean background
            self.surface = "#FFFFFF"            # Crisp white card surface
            self.surface_alt = "#F1F5F9"        # Off-white
            self.border = "#E2E8F0"             # Subtle card border
            self.border_subtle = "#F1F5F9"

            # Text (WCAG AAA High Contrast Dark Slate)
            self.text_primary = "#0F172A"       # Deep dark slate text
            self.text_secondary = "#334155"     # Medium slate
            self.text_muted = "#64748B"         # Muted label slate

            # Deep Teal & Healthtech Accents (matching reference PDF)
            self.primary = "#0F5147"            # Deep pine teal (Hero & Primary button)
            self.primary_dark = "#0F5147"
            self.primary_hover = "#0D453C"

            self.pill_active_bg = "#E6F4F1"
            self.pill_active_text = "#0F5147"
            self.pill_inactive_bg = "#FFFFFF"
            self.pill_inactive_text = "#475569"

            self.tag_bg = "#E6F4F1"             # Soft light teal badge
            self.tag_text = "#0F5147"

            self.hero_bg = "#0F5147"            # Deep pine teal hero card

            # Backward compatibility aliases
            self.blue_primary = self.primary
            self.blue_hover = self.primary_hover
            self.blue_pill_bg = self.tag_bg
            self.blue_pill_text = self.tag_text

            self.pink_primary = "#00695C"
            self.pink_hover = "#004D40"
            self.pink_pill_bg = "#E6F4F1"
            self.pink_pill_text = "#0F5147"

            self.banner_bg = "#FEF3C7"          # Warm amber
            self.banner_border = "#FDE68A"
            self.banner_text = "#92400E"
            self.banner_btn = "#78350F"
