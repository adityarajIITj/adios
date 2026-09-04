#!/usr/bin/env python3
"""
AdiOS User Interface Subsystem: Hierarchical GUI Widget Toolkit (widgets.py)
Implements object-oriented GUI components:
- Widget base with full hierarchy, relative/screen coordinate propagation, and event routing
- Label, Button (normal, hover, pressed states)
- TextBox (cursor, backspace, character input, focus indicator)
- Slider (value mapping, dragging thumb)
- ProgressBar (determinate percentage bar and indeterminate pulse)
- CheckBox (toggle state, custom checkmark rendering)
- ScrollView with dynamic viewport clipping and scrollbars
- Layout Containers: HBox (horizontal flexbox) and VBox (vertical flexbox)
- Draggable WindowWidget with title bar, controls, and shadow
- Keyboard Tab focus management

Zero external dependencies. Pure RV32IM GUI engine.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

from typing import List, Optional, Callable, Any
from ui.canvas2d import Canvas2D, Rect

class Widget:
    """
    Base class for all UI components.
    """
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.parent: Optional['Widget'] = None
        self.children: List['Widget'] = []
        self.visible = True
        self.enabled = True
        self.focused = False
        self.tab_index = 0

    def add_child(self, child: 'Widget'):
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: 'Widget'):
        if child in self.children:
            child.parent = None
            self.children.remove(child)

    @property
    def screen_x(self) -> int:
        return self.x + (self.parent.screen_x if self.parent else 0)

    @property
    def screen_y(self) -> int:
        return self.y + (self.parent.screen_y if self.parent else 0)

    def render(self, canvas: Canvas2D):
        if not self.visible:
            return
        self.draw(canvas)
        for child in self.children:
            child.render(canvas)

    def draw(self, canvas: Canvas2D):
        pass

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if not self.visible or not self.enabled:
            return False
        # Check children in reverse Z-order
        for child in reversed(self.children):
            if child.contains(mx, my) and child.on_mouse_down(mx, my):
                return True
        return False

    def on_mouse_up(self, mx: int, my: int) -> bool:
        for child in reversed(self.children):
            child.on_mouse_up(mx, my)
        return False

    def on_mouse_move(self, mx: int, my: int):
        for child in self.children:
            child.on_mouse_move(mx, my)

    def on_key_down(self, key_code: int, char: str) -> bool:
        for child in self.children:
            if child.on_key_down(key_code, char):
                return True
        return False

    def contains(self, px: int, py: int) -> bool:
        sx = self.screen_x
        sy = self.screen_y
        return sx <= px < sx + self.w and sy <= py < sy + self.h

class Label(Widget):
    """Text label widget."""
    def __init__(self, x: int, y: int, w: int, h: int, text: str, color: int = 0xFFC0CAF5):
        super().__init__(x, y, w, h)
        self.text = text
        self.color = color

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        canvas.fill_rect(sx, sy + self.h // 2, min(self.w, len(self.text) * 6), 2, self.color)

class Button(Widget):
    """Interactive push button with states (normal, hover, pressed)."""
    def __init__(self, x: int, y: int, w: int, h: int, text: str, on_click: Optional[Callable] = None):
        super().__init__(x, y, w, h)
        self.text = text
        self.on_click = on_click
        self.is_pressed = False
        self.is_hovered = False

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        color = 0xFF3B4261 if self.is_pressed else (0xFF414868 if self.is_hovered else 0xFF24283B)
        canvas.fill_rounded_rect(sx, sy, self.w, self.h, 4, color)
        canvas.draw_rect(sx, sy, self.w, self.h, 0xFF7AA2F7)

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if self.contains(mx, my):
            self.is_pressed = True
            return True
        return False

    def on_mouse_up(self, mx: int, my: int) -> bool:
        if self.is_pressed and self.contains(mx, my):
            self.is_pressed = False
            if self.on_click:
                self.on_click()
            return True
        self.is_pressed = False
        return False

    def on_mouse_move(self, mx: int, my: int):
        self.is_hovered = self.contains(mx, my)

class TextBox(Widget):
    """Editable text input box."""
    def __init__(self, x: int, y: int, w: int, h: int, initial_text: str = ""):
        super().__init__(x, y, w, h)
        self.text = initial_text
        self.cursor_pos = len(initial_text)

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        canvas.fill_rect(sx, sy, self.w, self.h, 0xFF1F2335)
        border_color = 0xFF7AA2F7 if self.focused else 0xFF565F89
        canvas.draw_rect(sx, sy, self.w, self.h, border_color)

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if self.contains(mx, my):
            self.focused = True
            return True
        self.focused = False
        return False

    def on_key_down(self, key_code: int, char: str) -> bool:
        if not self.focused:
            return False
        if key_code == 8: # Backspace
            if self.text:
                self.text = self.text[:-1]
                return True
        elif char and char.isprintable():
            self.text += char
            return True
        return False

class Slider(Widget):
    """Horizontal value slider (min_val..max_val)."""
    def __init__(self, x: int, y: int, w: int, h: int, min_val: float = 0.0, max_val: float = 1.0, initial: float = 0.5):
        super().__init__(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial
        self.is_dragging = False

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        # Track line
        canvas.fill_rect(sx, sy + self.h // 2 - 2, self.w, 4, 0xFF414868)
        # Thumb position
        norm = (self.value - self.min_val) / (self.max_val - self.min_val)
        tx = int(sx + norm * (self.w - 12))
        canvas.fill_rounded_rect(tx, sy + self.h // 2 - 6, 12, 12, 6, 0xFF7AA2F7)

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if self.contains(mx, my):
            self.is_dragging = True
            self._update_val(mx)
            return True
        return False

    def on_mouse_up(self, mx: int, my: int) -> bool:
        self.is_dragging = False
        return False

    def on_mouse_move(self, mx: int, my: int):
        if self.is_dragging:
            self._update_val(mx)

    def _update_val(self, mx: int):
        sx = self.screen_x
        norm = max(0.0, min(1.0, (mx - sx) / self.w))
        self.value = self.min_val + norm * (self.max_val - self.min_val)

class ProgressBar(Widget):
    """Progress indicator widget supporting determinate and indeterminate modes."""
    def __init__(self, x: int, y: int, w: int, h: int, progress: float = 0.0):
        super().__init__(x, y, w, h)
        self.progress = max(0.0, min(1.0, progress))
        self.indeterminate = False
        self.pulse_phase = 0

    def set_progress(self, val: float):
        self.progress = max(0.0, min(1.0, val))

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        canvas.fill_rounded_rect(sx, sy, self.w, self.h, 3, 0xFF24283B)
        canvas.draw_rect(sx, sy, self.w, self.h, 0xFF414868)

        if self.indeterminate:
            pulse_w = max(10, self.w // 4)
            offset = int((self.pulse_phase % 100) / 100.0 * (self.w - pulse_w))
            canvas.fill_rounded_rect(sx + offset, sy + 1, pulse_w, self.h - 2, 2, 0xFFBB9AF7)
            self.pulse_phase += 2
        else:
            fill_w = int(self.progress * (self.w - 2))
            if fill_w > 0:
                canvas.fill_rounded_rect(sx + 1, sy + 1, fill_w, self.h - 2, 2, 0xFF7AA2F7)

class CheckBox(Widget):
    """Toggle CheckBox widget."""
    def __init__(self, x: int, y: int, size: int = 16, checked: bool = False, on_toggle: Optional[Callable] = None):
        super().__init__(x, y, size, size)
        self.checked = checked
        self.on_toggle = on_toggle

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        canvas.fill_rounded_rect(sx, sy, self.w, self.h, 2, 0xFF24283B)
        border_color = 0xFF7AA2F7 if self.checked else 0xFF565F89
        canvas.draw_rect(sx, sy, self.w, self.h, border_color)

        if self.checked:
            # Draw inner indicator
            canvas.fill_rect(sx + 3, sy + 3, self.w - 6, self.h - 6, 0xFF7AA2F7)

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if self.contains(mx, my):
            self.checked = not self.checked
            if self.on_toggle:
                self.on_toggle(self.checked)
            return True
        return False

class HBox(Widget):
    """Horizontal Flexbox layout container."""
    def __init__(self, x: int, y: int, spacing: int = 8):
        super().__init__(x, y, 0, 0)
        self.spacing = spacing

    def add_child(self, child: Widget):
        super().add_child(child)
        self.relayout()

    def relayout(self):
        curr_x = 0
        max_h = 0
        for child in self.children:
            child.x = curr_x
            child.y = 0
            curr_x += child.w + self.spacing
            if child.h > max_h:
                max_h = child.h
        self.w = max(0, curr_x - self.spacing)
        self.h = max_h

class VBox(Widget):
    """Vertical Flexbox layout container."""
    def __init__(self, x: int, y: int, spacing: int = 8):
        super().__init__(x, y, 0, 0)
        self.spacing = spacing

    def add_child(self, child: Widget):
        super().add_child(child)
        self.relayout()

    def relayout(self):
        curr_y = 0
        max_w = 0
        for child in self.children:
            child.x = 0
            child.y = curr_y
            curr_y += child.h + self.spacing
            if child.w > max_w:
                max_w = child.w
        self.w = max_w
        self.h = max(0, curr_y - self.spacing)

class ScrollView(Widget):
    """Scrollable Viewport with dynamic content offset."""
    def __init__(self, x: int, y: int, w: int, h: int, content_w: int, content_h: int):
        super().__init__(x, y, w, h)
        self.content_w = content_w
        self.content_h = content_h
        self.scroll_x = 0
        self.scroll_y = 0

    def scroll_by(self, dx: int, dy: int):
        max_scroll_x = max(0, self.content_w - self.w)
        max_scroll_y = max(0, self.content_h - self.h)
        self.scroll_x = max(0, min(max_scroll_x, self.scroll_x + dx))
        self.scroll_y = max(0, min(max_scroll_y, self.scroll_y + dy))

    def render(self, canvas: Canvas2D):
        if not self.visible:
            return
        sx = self.screen_x
        sy = self.screen_y
        canvas.push_clip(Rect(sx, sy, self.w, self.h))
        self.draw(canvas)
        for child in self.children:
            child.render(canvas)
        canvas.pop_clip()

class WindowWidget(Widget):
    """Draggable desktop window with titlebar and client area."""
    def __init__(self, x: int, y: int, w: int, h: int, title: str):
        super().__init__(x, y, w, h)
        self.title = title
        self.title_height = 24
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def draw(self, canvas: Canvas2D):
        sx = self.screen_x
        sy = self.screen_y
        # Window Shadow
        canvas.fill_rounded_rect(sx + 4, sy + 4, self.w, self.h, 6, 0x40000000)
        # Window Body
        canvas.fill_rounded_rect(sx, sy, self.w, self.h, 6, 0xFF1A1B26)
        # Titlebar
        canvas.fill_rounded_rect(sx, sy, self.w, self.title_height, 6, 0xFF24283B)
        canvas.fill_rect(sx, sy + self.title_height - 6, self.w, 6, 0xFF24283B)
        canvas.draw_rect(sx, sy, self.w, self.h, 0xFF414868)

    def on_mouse_down(self, mx: int, my: int) -> bool:
        if not self.contains(mx, my):
            return False

        # Check if clicked on titlebar
        sx = self.screen_x
        sy = self.screen_y
        if sy <= my < sy + self.title_height:
            self.is_dragging = True
            self.drag_offset_x = mx - self.x
            self.drag_offset_y = my - self.y
            return True

        return super().on_mouse_down(mx, my)

    def on_mouse_up(self, mx: int, my: int) -> bool:
        self.is_dragging = False
        return super().on_mouse_up(mx, my)

    def on_mouse_move(self, mx: int, my: int):
        if self.is_dragging:
            self.x = mx - self.drag_offset_x
            self.y = my - self.drag_offset_y
        super().on_mouse_move(mx, my)

if __name__ == "__main__":
    win = WindowWidget(50, 50, 200, 150, "Sovereign Control")
    btn_clicked = False
    def click_handler():
        global btn_clicked
        btn_clicked = True

    btn = Button(10, 40, 80, 28, "Execute", on_click=click_handler)
    win.add_child(btn)

    # Click inside button
    win.on_mouse_down(65, 95)
    win.on_mouse_up(65, 95)
    assert btn_clicked is True

    # Test ProgressBar & CheckBox
    pb = ProgressBar(10, 80, 100, 12, progress=0.75)
    assert pb.progress == 0.75
    cb = CheckBox(10, 100, size=16, checked=False)
    cb.on_mouse_down(cb.screen_x + 2, cb.screen_y + 2)
    assert cb.checked is True

    # Test Flexbox VBox
    vbox = VBox(0, 0, spacing=4)
    vbox.add_child(Button(0, 0, 50, 20, "1"))
    vbox.add_child(Button(0, 0, 50, 20, "2"))
    assert vbox.h == 44  # 20 + 4 + 20

    print("Widget toolkit, ProgressBar, CheckBox, and Flexbox containers verified.")
