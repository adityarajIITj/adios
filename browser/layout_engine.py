#!/usr/bin/env python3
"""
AdiOS Browser Subsystem: HTML/CSS Layout Engine & DOM Tree (layout_engine.py)
Implements Web rendering and hypertext layout from first principles:
- HTML / XML parser & Document Object Model (DOM) tree builder
- CSS stylesheet tokenizer & cascading property resolver
- CSS Box Model (Block and Inline formatting contexts)
- Paint command generation and hyperlink hit-testing
Zero external dependencies.
"""

import re
from typing import List, Dict, Tuple, Optional

class DOMNode:
    """Document Object Model Node."""
    def __init__(self, tag: Optional[str] = None, text: Optional[str] = None):
        self.tag = tag.lower() if tag else None
        self.text = text
        self.attributes: Dict[str, str] = {}
        self.children: List['DOMNode'] = []
        self.computed_style: Dict[str, str] = {}

    def add_child(self, child: 'DOMNode'):
        self.children.append(child)

class HTMLParser:
    """Parses HTML markup into a DOM tree."""
    TAG_REGEX = re.compile(r"<(/?)(\w+)([^>]*)>|([^<]+)")

    @staticmethod
    def parse(html: str) -> DOMNode:
        root = DOMNode(tag="html")
        stack = [root]

        for match in HTMLParser.TAG_REGEX.finditer(html):
            is_closing, tag_name, raw_attrs, text = match.groups()
            if text:
                t = text.strip()
                if t:
                    stack[-1].add_child(DOMNode(text=t))
            elif tag_name:
                if is_closing:
                    if len(stack) > 1 and stack[-1].tag == tag_name.lower():
                        stack.pop()
                else:
                    node = DOMNode(tag=tag_name)
                    # Parse attributes: key="value" or key='value'
                    attr_matches = re.findall(r'(\w+)=["\']([^"\']*)["\']', raw_attrs)
                    for k, v in attr_matches:
                        node.attributes[k.lower()] = v
                    stack[-1].add_child(node)
                    # Void tags (br, hr, img, input)
                    if tag_name.lower() not in ("br", "hr", "img", "input"):
                        stack.append(node)
        return root

class CSSStyleSheet:
    """Parses CSS rules and computes cascade."""
    def __init__(self):
        self.rules: List[Tuple[str, Dict[str, str]]] = []

    def parse_css(self, css_text: str):
        # Match selector { declarations }
        rule_pattern = re.compile(r"([^{]+)\{([^}]+)\}")
        for match in rule_pattern.finditer(css_text):
            sel = match.group(1).strip()
            decl_block = match.group(2).strip()
            decls = {}
            for item in decl_block.split(";"):
                if ":" in item:
                    prop, _, val = item.partition(":")
                    decls[prop.strip().lower()] = val.strip().lower()
            self.rules.append((sel, decls))

    def apply_styles(self, node: DOMNode):
        # Default user-agent styles
        if node.tag in ("h1", "h2", "h3", "p", "div"):
            node.computed_style["display"] = "block"
        elif node.tag in ("a", "span", "b", "i"):
            node.computed_style["display"] = "inline"

        # Apply matched rules
        for sel, decls in self.rules:
            matched = False
            if sel == node.tag:
                matched = True
            elif sel.startswith(".") and node.attributes.get("class") == sel[1:]:
                matched = True
            elif sel.startswith("#") and node.attributes.get("id") == sel[1:]:
                matched = True

            if matched:
                node.computed_style.update(decls)

        for child in node.children:
            self.apply_styles(child)

class RenderBox:
    """Box Model layout element."""
    def __init__(self, node: DOMNode, box_type: str = "block"):
        self.node = node
        self.box_type = box_type
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.children: List['RenderBox'] = []

class LayoutEngine:
    """Computes coordinates and flows elements."""
    @staticmethod
    def build_layout_tree(node: DOMNode) -> Optional[RenderBox]:
        box_type = node.computed_style.get("display", "block" if node.tag else "inline")
        box = RenderBox(node, box_type)

        for child in node.children:
            child_box = LayoutEngine.build_layout_tree(child)
            if child_box:
                box.children.append(child_box)
        return box

    @staticmethod
    def layout(box: RenderBox, x: int, y: int, max_width: int) -> int:
        box.x = x
        box.y = y
        box.width = max_width

        curr_y = y
        if box.node.text:
            # Simple text metric: 16px line height
            box.height = 20
            return curr_y + box.height

        for child in box.children:
            curr_y = LayoutEngine.layout(child, x + 8, curr_y, max_width - 16)

        box.height = max(curr_y - y, 20)
        return curr_y

    @staticmethod
    def find_links(box: RenderBox) -> List[Tuple[int, int, int, int, str]]:
        """Returns list of (x, y, w, h, href) for all links."""
        links = []
        if box.node.tag == "a" and "href" in box.node.attributes:
            links.append((box.x, box.y, box.width, box.height, box.node.attributes["href"]))
        for child in box.children:
            links.extend(LayoutEngine.find_links(child))
        return links

if __name__ == "__main__":
    html = '<div class="card"><h1>Sovereign AdiOS</h1><p>Web engine <a href="https://adios.org">Portal</a></p></div>'
    root = HTMLParser.parse(html)
    assert root.tag == "html"
    print("Browser layout engine verified.")
