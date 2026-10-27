from src.litmus.schemas import Modality, Segment
from src.litmus.tree import SegmentTree


def test_tree_cycle():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    # Manually create cycle for validation test
    root.parent_id = "s0"
    assert tree.validate() is False
