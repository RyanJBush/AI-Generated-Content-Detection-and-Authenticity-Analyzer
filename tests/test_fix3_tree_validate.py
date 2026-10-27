from src.litmus.schemas import Modality, Segment
from src.litmus.tree import SegmentTree


def test_tree_validate_rejects_dangling_parent():
    tree = SegmentTree()
    tree.add_segment(Segment("s0", None, Modality.TEXT, ["utf8_decode"]))
    tree.add_segment(Segment("s1", "s0", Modality.TEXT, ["extract"]))
    assert tree.validate() is True

    # Bypass add_segment: a non-root segment whose parent is absent
    tree.segments["s2"] = Segment("s2", "missing", Modality.TEXT, ["extract"])
    assert tree.validate() is False


def test_tree_validate_rejects_parent_removed_after_add():
    tree = SegmentTree()
    tree.add_segment(Segment("s0", None, Modality.TEXT, ["utf8_decode"]))
    tree.add_segment(Segment("s1", "s0", Modality.TEXT, ["extract"]))
    tree.add_segment(Segment("s2", "s1", Modality.TEXT, ["extract"]))

    del tree.segments["s1"]
    assert tree.validate() is False
