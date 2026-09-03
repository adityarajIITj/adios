#!/usr/bin/env python3
"""
Test Suite: DolDoc Universal Hypertext Engine
Verifies:
1. DolDoc stream parsing (colors, links, buttons)
2. Document cell grid mapping
3. Mouse hit-testing for interactive hyperlinks and buttons
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from doldoc import DolDocParser, DolDocument, DocText, DocLink, DocButton

def test_doldoc_suite():
    print("[Test DolDoc] Testing DolDoc Universal Hypertext Engine...")

    # 1. Test Stream Parsing
    print("  -> Testing DolDoc markup stream parser...")
    raw = "Welcome to $RED$AdiOS$DEFAULT$! Click $LK,\"StarFlight 3D\",A=\"flight3d\"$ or press $BT,\"Launch\",LM=\"exec_starflight\"$."
    parser = DolDocParser()
    nodes = parser.parse(raw)

    assert any(isinstance(n, DocText) and n.fg == "RED" for n in nodes), "RED text node missing"
    assert any(isinstance(n, DocLink) and n.label == "StarFlight 3D" for n in nodes), "StarFlight link missing"
    assert any(isinstance(n, DocButton) and n.label == "Launch" for n in nodes), "Launch button missing"
    print("  -> [PASS] DolDoc stream parser verified.")

    # 2. Test Document Layout & Hit-Testing
    print("  -> Testing DolDocument cell grid and hit-testing...")
    doc = DolDocument(max_cols=60, max_rows=20)
    doc.load_stream(raw)

    # Find the link coordinates and test hit_test()
    link_elem = None
    for row, col_start, col_end, node in doc.interactive_elements:
        if isinstance(node, DocLink):
            link_elem = (row, col_start, col_end, node)
            break
    assert link_elem is not None, "Interactive link not registered in document"

    row, c_start, c_end, node = link_elem
    # Click right in the middle of the link
    mid_col = (c_start + c_end) // 2
    click_x = mid_col * 8 + 4
    click_y = row * 8 + 4

    hit = doc.hit_test(click_x, click_y)
    assert hit is not None, "Hit test failed to find link"
    assert isinstance(hit, DocLink) and hit.label == "StarFlight 3D", f"Hit test returned unexpected: {hit}"
    print(f"  -> Mouse click at ({click_x}, {click_y}) hit: [{hit.label}] -> Action: {hit.action_type}={hit.target}")
    print("  -> [PASS] DolDoc interactive hit-testing verified.")

    print("\n[Test DolDoc] ALL DOLDOC HYPERTEXT ENGINE TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_doldoc_suite()
