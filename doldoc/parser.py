#!/usr/bin/env python3
"""
DolDoc Stream Parser for AdiOS
Inspired by Terry A. Davis's DolDoc hypertext document format in TempleOS.
Parses formatted text, colors, hyperlinks, buttons, macros, and trees.
"""

import re

# DolDoc Colors
DOC_COLORS = {
    "BLACK":   0x00000000,
    "BLUE":    0x007AA2F7,
    "GREEN":   0x009ECE6A,
    "CYAN":    0x007DCFFF,
    "RED":     0x00F7768E,
    "MAGENTA": 0x00BB9AF7,
    "YELLOW":  0x00E0AF68,
    "WHITE":   0x00FFFFFF,
    "DEFAULT": 0x00C0CAF5
}

class DocNode: pass

class DocText(DocNode):
    def __init__(self, text, fg="DEFAULT", bg=None, underline=False, bold=False):
        self.text = text
        self.fg = fg
        self.bg = bg
        self.underline = underline
        self.bold = bold

    def __repr__(self):
        return f"DocText({repr(self.text)}, fg={self.fg})"

class DocLink(DocNode):
    def __init__(self, label, action_type, target):
        self.label = label
        self.action_type = action_type # "LK", "FI" (file), "MA" (macro)
        self.target = target

    def __repr__(self):
        return f"DocLink({repr(self.label)}, {self.action_type}={repr(self.target)})"

class DocButton(DocNode):
    def __init__(self, label, macro):
        self.label = label
        self.macro = macro

    def __repr__(self):
        return f"DocButton({repr(self.label)}, macro={repr(self.macro)})"

class DocTree(DocNode):
    def __init__(self, label, collapsed=True, children=None):
        self.label = label
        self.collapsed = collapsed
        self.children = children or []

class DolDocParser:
    def __init__(self):
        pass

    def parse(self, raw_stream):
        """Parses raw DolDoc markup containing $...$ tags into a list of DocNodes."""
        nodes = []
        curr_fg = "DEFAULT"
        curr_bg = None
        curr_ul = False

        # Regex to split on DolDoc tags like $RED$, $LK,"click me",A="run"$
        parts = re.split(r'(\$[^\$]*\$)', raw_stream)

        for part in parts:
            if not part: continue

            if part.startswith("$") and part.endswith("$"):
                tag_content = part[1:-1].strip()
                if not tag_content: # Escaped $$ -> single $
                    nodes.append(DocText("$", curr_fg, curr_bg, curr_ul))
                    continue

                tag_parts = [p.strip() for p in tag_content.split(",")]
                cmd = tag_parts[0].upper()

                # 1. Color Tags ($RED$, $BLUE$, $DEFAULT$)
                if cmd in DOC_COLORS:
                    curr_fg = cmd
                    continue
                elif cmd == "BG" and len(tag_parts) > 1:
                    curr_bg = tag_parts[1].upper()
                    continue

                # 2. Text Attributes ($UL,1$, $UL,0$)
                if cmd == "UL" and len(tag_parts) > 1:
                    curr_ul = (tag_parts[1] == "1")
                    continue

                # 3. Hyperlink ($LK,"Click Me",A="action"$)
                if cmd == "LK":
                    label = tag_parts[1].strip('"') if len(tag_parts) > 1 else "Link"
                    target = ""
                    action_type = "LK"
                    for p in tag_parts[2:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            action_type = k.strip()
                            target = v.strip().strip('"')
                    nodes.append(DocLink(label, action_type, target))
                    continue

                # 4. Button ($BT,"Button Label",LM="macro"$)
                if cmd == "BT":
                    label = tag_parts[1].strip('"') if len(tag_parts) > 1 else "Button"
                    macro = ""
                    for p in tag_parts[2:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            macro = v.strip().strip('"')
                    nodes.append(DocButton(label, macro))
                    continue

                # 5. Tree ($TR,"Section"$)
                if cmd == "TR":
                    label = tag_parts[1].strip('"') if len(tag_parts) > 1 else "Tree"
                    nodes.append(DocTree(label, collapsed=True))
                    continue

            else:
                # Regular text
                nodes.append(DocText(part, curr_fg, curr_bg, curr_ul))

        return nodes
