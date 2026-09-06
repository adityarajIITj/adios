#!/usr/bin/env python3
"""
AdiOS Minimalist Modern Theme Engine (desktop/theme.py)
Provides clean, subdued, professional color palettes:
- Nordic Slate (Default: refined dark slate with crisp ice-blue accents)
- Monochrome Silver (Minimalist graphite with clean silver-white typography)
- Arctic Minimal (Clean high-contrast light theme with deep charcoal ink)
- Emerald Code (Subtle dark engineering palette with GitHub-style green)

Strict Zero Emoji Policy.
"""

from typing import Dict, Any, NamedTuple

class Palette(NamedTuple):
    name: str
    desktop_bg: int
    taskbar_bg: int
    taskbar_border: int
    win_bg: int
    win_border: int
    win_title_active: int
    win_title_inactive: int
    win_title_text: int
    text_primary: int
    text_muted: int
    text_highlight: int
    accent_primary: int
    accent_secondary: int
    btn_bg: int
    btn_border: int
    btn_text: int
    btn_hover: int
    gutter_bg: int
    gutter_line: int
    card_bg: int
    card_border: int

# 1. Nordic Slate (Refined modern dark minimalism)
PALETTE_NORDIC_SLATE = Palette(
    name="Nordic Slate",
    desktop_bg=0x000F141C,
    taskbar_bg=0x000B0F17,
    taskbar_border=0x001E2633,
    win_bg=0x00131822,
    win_border=0x00253041,
    win_title_active=0x001B2331,
    win_title_inactive=0x0010141D,
    win_title_text=0x00E2E8F0,
    text_primary=0x00F1F5F9,
    text_muted=0x0064748B,
    text_highlight=0x0038BDF8,  # Crisp Ice Blue
    accent_primary=0x0038BDF8,
    accent_secondary=0x000EA5E9,
    btn_bg=0x001C2433,
    btn_border=0x002C394E,
    btn_text=0x00E2E8F0,
    btn_hover=0x00243045,
    gutter_bg=0x000E131A,
    gutter_line=0x001C2533,
    card_bg=0x00151B26,
    card_border=0x00232E40
)

# 2. Monochrome Silver (Pure minimalist studio graphite)
PALETTE_MONOCHROME = Palette(
    name="Monochrome Silver",
    desktop_bg=0x00111215,
    taskbar_bg=0x000D0E10,
    taskbar_border=0x0022242A,
    win_bg=0x0016181C,
    win_border=0x002B2E36,
    win_title_active=0x001F2228,
    win_title_inactive=0x00131518,
    win_title_text=0x00F3F4F6,
    text_primary=0x00F9FAFB,
    text_muted=0x006B7280,
    text_highlight=0x00D1D5DB,  # Clean Silver White
    accent_primary=0x009CA3AF,
    accent_secondary=0x006B7280,
    btn_bg=0x0022252B,
    btn_border=0x00373B45,
    btn_text=0x00F3F4F6,
    btn_hover=0x002D313A,
    gutter_bg=0x00101215,
    gutter_line=0x00202329,
    card_bg=0x00181A1F,
    card_border=0x00292C34
)

# 3. Arctic Minimal (Clean daylight Scandinavian minimalism)
PALETTE_ARCTIC = Palette(
    name="Arctic Minimal",
    desktop_bg=0x00E8ECF2,
    taskbar_bg=0x00F8FAFC,
    taskbar_border=0x00CBD5E1,
    win_bg=0x00FFFFFF,
    win_border=0x00CBD5E1,
    win_title_active=0x00F1F5F9,
    win_title_inactive=0x00F8FAFC,
    win_title_text=0x000F172A,
    text_primary=0x000F172A,
    text_muted=0x0064748B,
    text_highlight=0x002563EB,  # Royal Minimal Blue
    accent_primary=0x002563EB,
    accent_secondary=0x001D4ED8,
    btn_bg=0x00F1F5F9,
    btn_border=0x00CBD5E1,
    btn_text=0x000F172A,
    btn_hover=0x00E2E8F0,
    gutter_bg=0x00F8FAFC,
    gutter_line=0x00E2E8F0,
    card_bg=0x00F8FAFC,
    card_border=0x00E2E8F0
)

# 4. Emerald Code (Subtle minimalist dark terminal)
PALETTE_EMERALD = Palette(
    name="Emerald Code",
    desktop_bg=0x000D1117,
    taskbar_bg=0x00090D12,
    taskbar_border=0x001B222C,
    win_bg=0x00121820,
    win_border=0x00222D3A,
    win_title_active=0x0018202B,
    win_title_inactive=0x000F141B,
    win_title_text=0x00E6EDF3,
    text_primary=0x00F0F6FC,
    text_muted=0x005E6A7A,
    text_highlight=0x002EA043,  # Subtle Engineering Green
    accent_primary=0x002EA043,
    accent_secondary=0x00238636,
    btn_bg=0x001A2330,
    btn_border=0x002D3B4E,
    btn_text=0x00E6EDF3,
    btn_hover=0x00222F40,
    gutter_bg=0x000B0F15,
    gutter_line=0x001C2532,
    card_bg=0x00141B24,
    card_border=0x00212B38
)

THEMES: Dict[str, Palette] = {
    "nordic": PALETTE_NORDIC_SLATE,
    "mono": PALETTE_MONOCHROME,
    "arctic": PALETTE_ARCTIC,
    "emerald": PALETTE_EMERALD,
}

class ThemeManager:
    """
    Singleton Theme Manager coordinating active visual styling across all AdiOS windows.
    """
    _instance = None

    def __init__(self):
        self._current_theme_key = "nordic"
        self._palette = PALETTE_NORDIC_SLATE

    @classmethod
    def get_instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def current_key(self) -> str:
        return self._current_theme_key

    @property
    def palette(self) -> Palette:
        return self._palette

    def set_theme(self, key: str) -> bool:
        if key in THEMES:
            self._current_theme_key = key
            self._palette = THEMES[key]
            return True
        return False

    def next_theme(self) -> str:
        keys = list(THEMES.keys())
        idx = (keys.index(self._current_theme_key) + 1) % len(keys)
        self.set_theme(keys[idx])
        return self._current_theme_key
