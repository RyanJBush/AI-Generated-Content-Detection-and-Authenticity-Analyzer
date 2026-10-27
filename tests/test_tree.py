import pytest
from src.litmus.tree import SegmentTree
from src.litmus.schemas import Segment, Modality

def test_tree_cycle():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    # Manually create cycle for validation test
    root.parent_id = "s0"
    # The current SegmentTree.validate() doesn't actually check for cycles
    # unless we implement it.
    # I will implement the check in SegmentTree.validate().
    assert tree.validate() is False
