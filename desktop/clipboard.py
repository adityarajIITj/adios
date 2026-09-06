#!/usr/bin/env python3
"""
AdiOS Sovereign System Clipboard (desktop/clipboard.py)
Unified clipboard management supporting:
1. Authoritative in-memory clipboard buffer (guaranteeing 100% testability, zero stutter, crash-free)
2. Pygame scrap synchronization when an active display window is initialized

Strict Zero Emoji Policy.
"""

from typing import Optional

class SovereignClipboard:
    """
    Sovereign cross-platform clipboard manager singleton.
    """
    _instance: Optional["SovereignClipboard"] = None
    _in_memory_text: str = ""

    @classmethod
    def get_instance(cls) -> "SovereignClipboard":
        if cls._instance is None:
            cls._instance = SovereignClipboard()
        return cls._instance

    def set_text(self, text: str):
        """Sets clipboard content across available backends."""
        self._in_memory_text = str(text)

        # Synchronize with Pygame scrap only if an actual display surface is active
        try:
            import pygame
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                if hasattr(pygame.scrap, "put_text"):
                    pygame.scrap.put_text(self._in_memory_text)
        except Exception:
            pass

    def get_text(self) -> str:
        """Retrieves clipboard content from available backends."""
        # Check Pygame scrap first if active display surface exists
        try:
            import pygame
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                if hasattr(pygame.scrap, "get_text"):
                    txt = pygame.scrap.get_text()
                    if txt:
                        self._in_memory_text = txt
                        return txt
        except Exception:
            pass

        return self._in_memory_text

    def clear(self):
        """Clears clipboard content."""
        self.set_text("")

    def has_text(self) -> bool:
        """Checks if clipboard currently contains text."""
        return len(self.get_text()) > 0
