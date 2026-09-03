#!/usr/bin/env python3
"""
Test Suite: Block X Web Engine & Hypertext Layout Browser
Verifies:
1. browser/layout_engine: HTML/XML tokenizer & DOM tree creation
2. browser/layout_engine: CSS stylesheet parsing & cascade styling (tag, class, ID)
3. browser/layout_engine: Box model layout flow & vertical stacking
4. browser/layout_engine: Hyperlink hitbox extraction
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from browser.layout_engine import HTMLParser, CSSStyleSheet, LayoutEngine, DOMNode

def test_browser_block_x_suite():
    print("[Test Browser Block X] Initializing Web Engine & Layout Verification...")

    # 1. Test HTML Tokenizer & DOM Tree
    print("  -> Testing HTML Parser & DOM Tree Builder...")
    html = """
    <div id="main" class="container">
        <h1>Sovereign Hypertext Browser</h1>
        <p>Explore the decentralized cyberverse.</p>
        <a href="adios://kernel/docs">Kernel Reference</a>
    </div>
    """
    root = HTMLParser.parse(html)
    assert root.tag == "html"
    assert len(root.children) >= 1

    div_node = root.children[0]
    assert div_node.tag == "div"
    assert div_node.attributes["id"] == "main"
    assert div_node.attributes["class"] == "container"
    assert len(div_node.children) >= 3 # h1, p, a
    print("  -> [PASS] HTML parsing & DOM tree creation verified.")

    # 2. Test CSS Parser & Cascading Style Computation
    print("  -> Testing CSS Parser & Cascading Style Resolver...")
    css = """
    div { background-color: #1a1a24; }
    .container { color: #00ffcc; width: 600px; }
    #main { border: 1px solid #333344; }
    h1 { font-size: 24px; }
    """
    sheet = CSSStyleSheet()
    sheet.parse_css(css)
    assert len(sheet.rules) == 4

    sheet.apply_styles(root)
    # div_node matched div, .container, and #main!
    assert div_node.computed_style["background-color"] == "#1a1a24"
    assert div_node.computed_style["color"] == "#00ffcc"
    assert div_node.computed_style["width"] == "600px"
    assert div_node.computed_style["border"] == "1px solid #333344"
    print("  -> [PASS] CSS cascade styling verified.")

    # 3. Test Box Model Layout Flow
    print("  -> Testing Box Model Geometry & Layout Computation...")
    layout_tree = LayoutEngine.build_layout_tree(root)
    assert layout_tree is not None

    total_height = LayoutEngine.layout(layout_tree, x=20, y=30, max_width=640)
    assert layout_tree.x == 20
    assert layout_tree.y == 30
    assert layout_tree.width == 640
    assert layout_tree.height > 50
    assert total_height > 30
    print("  -> [PASS] Box model layout & geometry verified.")

    # 4. Test Hyperlink Hitbox Extraction
    print("  -> Testing Hyperlink Hitbox Detection...")
    links = LayoutEngine.find_links(layout_tree)
    assert len(links) == 1
    lx, ly, lw, lh, href = links[0]
    assert href == "adios://kernel/docs"
    assert lw > 0 and lh > 0
    print("  -> [PASS] Hyperlink extraction & hit-testing verified.")

    print("\n[Test Browser Block X] ALL BLOCK X BROWSER & LAYOUT TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_browser_block_x_suite()
