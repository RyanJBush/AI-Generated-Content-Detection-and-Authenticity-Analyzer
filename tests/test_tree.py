import pytest
from src.litmus.tree import SegmentTree
from src.litmus.schemas import Segment, Modality

def test_tree_basic():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    child = Segment("s1", "s0", Modality.TEXT, ["extract"])
    tree.add_segment(child)

    assert tree.validate() is True
    assert tree.get_ancestry("s1") == ["s0", "s1"]

def test_tree_invalid_parent():
    tree = SegmentTree()
    child = Segment("s1", "s0", Modality.TEXT, ["extract"])
    with pytest.raises(ValueError, match="Parent s0 must be added before child s1"):
        tree.add_segment(child)

def test_tree_multiple_roots():
    tree = SegmentTree()
    root1 = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    root2 = Segment("s0_alt", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root1)
    with pytest.raises(ValueError, match="Only one root segment allowed"):
        tree.add_segment(root2)

def test_tree_cycle():
    # Since we enforce parent-before-child, a direct cycle (s0 -> s0)
    # or (s0 -> s1 -> s0) is hard to create via add_segment.
    # But we can check the logic if we manually manipulate the dict.
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    # Manually create cycle
    root.parent_id = "s0"
    assert tree.validate() is False
