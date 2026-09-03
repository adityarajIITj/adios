#!/usr/bin/env python3
"""
DolDoc Interactive Document Engine for AdiOS
Renders rich text, colors, hyperlinks, buttons, and action macros directly to Framebuffer.
Provides hit-testing for mouse clicks.
"""

from .parser import DolDocParser, DocText, DocLink, DocButton, DocTree, DOC_COLORS

CHAR_WIDTH  = 8
CHAR_HEIGHT = 8

class DocCell:
    def __init__(self, char=" ", fg=0x00C0CAF5, bg=None, action=None):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.action = action # None or DocLink/DocButton

class DolDocument:
    def __init__(self, max_cols=76, max_rows=55):
        self.max_cols = max_cols
        self.max_rows = max_rows
        self.grid = [[DocCell() for _ in range(max_cols)] for _ in range(max_rows)]
        self.cursor_x = 0
        self.cursor_y = 0
        self.interactive_elements = [] # list of (row, col_start, col_end, node)

    def clear(self, bg=0x001A1B26):
        self.grid = [[DocCell(" ", bg=bg) for _ in range(self.max_cols)] for _ in range(self.max_rows)]
        self.cursor_x = 0
        self.cursor_y = 0
        self.interactive_elements.clear()

    def newline(self):
        self.cursor_x = 0
        self.cursor_y += 1
        if self.cursor_y >= self.max_rows:
            # Scroll up by 1 line
            self.grid.pop(0)
            self.grid.append([DocCell() for _ in range(self.max_cols)])
            self.cursor_y = self.max_rows - 1

    def write_char(self, ch, fg=0x00C0CAF5, bg=None, action=None):
        if ch == "\n":
            self.newline()
            return
        if self.cursor_x >= self.max_cols:
            self.newline()

        self.grid[self.cursor_y][self.cursor_x] = DocCell(ch, fg, bg, action)
        self.cursor_x += 1

    def append_node(self, node):
        if isinstance(node, DocText):
            fg_color = DOC_COLORS.get(node.fg, 0x00C0CAF5)
            bg_color = DOC_COLORS.get(node.bg, None) if node.bg else None
            for ch in node.text:
                self.write_char(ch, fg_color, bg_color)

        elif isinstance(node, DocLink):
            # Links rendered in Electric Blue or Cyan with [Link] brackets
            fg_color = DOC_COLORS["CYAN"]
            start_col = self.cursor_x
            link_text = f"[{node.label}]"
            for ch in link_text:
                self.write_char(ch, fg_color, action=node)
            end_col = self.cursor_x - 1
            self.interactive_elements.append((self.cursor_y, start_col, end_col, node))

        elif isinstance(node, DocButton):
            # Buttons rendered in Gold/Yellow with <Button> format
            fg_color = DOC_COLORS["YELLOW"]
            btn_text = f"<{node.label}>"
            start_col = self.cursor_x
            for ch in btn_text:
                self.write_char(ch, fg_color, action=node)
            end_col = self.cursor_x - 1
            self.interactive_elements.append((self.cursor_y, start_col, end_col, node))

    def load_stream(self, raw_doldoc):
        """Parses and appends a raw DolDoc stream into the document buffer."""
        parser = DolDocParser()
        nodes = parser.parse(raw_doldoc)
        for n in nodes:
            self.append_node(n)
        return nodes

    def hit_test(self, pixel_x, pixel_y, origin_x=0, origin_y=0):
        """Tests if a mouse pixel click falls on an interactive link or button."""
        rel_x = pixel_x - origin_x
        rel_y = pixel_y - origin_y
        if rel_x < 0 or rel_y < 0: return None

        col = rel_x // CHAR_WIDTH
        row = rel_y // CHAR_HEIGHT

        if 0 <= row < self.max_rows and 0 <= col < self.max_cols:
            cell = self.grid[row][col]
            if cell.action:
                return cell.action

        for elem_row, col_start, col_end, node in self.interactive_elements:
            if elem_row == row and col_start <= col <= col_end:
                return node
        return None

    def render_to_framebuffer(self, fb, font_dict, origin_x, origin_y, screen_w=640):
        """Renders the DolDoc character grid directly to the 640x480 Framebuffer."""
        for row in range(self.max_rows):
            py = origin_y + row * CHAR_HEIGHT
            if py + CHAR_HEIGHT > 480: break

            for col in range(self.max_cols):
                px = origin_x + col * CHAR_WIDTH
                if px + CHAR_WIDTH > screen_w: break

                cell = self.grid[row][col]
                ch = cell.char
                fg = cell.fg
                bitmap = font_dict.get(ch, font_dict.get(" ", b"\x00"*8))

                fg_bytes = bytes([fg & 0xFF, (fg >> 8) & 0xFF, (fg >> 16) & 0xFF, (fg >> 24) & 0xFF])

                for bit_y in range(CHAR_HEIGHT):
                    byte_val = bitmap[bit_y]
                    for bit_x in range(CHAR_WIDTH):
                        if (byte_val >> (7 - bit_x)) & 1:
                            off = ((py + bit_y) * screen_w + (px + bit_x)) * 4
                            fb[off:off+4] = fg_bytes
