import json

import pytest

from src.litmus.schemas import Modality, Segment, to_json
from src.litmus.tree import SegmentTree


def test_tree_mutation_atomicity():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    state_before = json.dumps(to_json(tree.segments), sort_keys=True)

    # Attempt to add second root
    root2 = Segment("s0_alt", None, Modality.TEXT, ["utf8_decode"])
    with pytest.raises(ValueError, match="Only one root"):
        tree.add_segment(root2)

    state_after = json.dumps(to_json(tree.segments), sort_keys=True)
    assert state_before == state_after
    assert tree.validate() is True

def test_tree_unknown_parent_atomicity():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    state_before = json.dumps(to_json(tree.segments), sort_keys=True)

    child = Segment("s1", "unknown", Modality.TEXT, ["extract"])
    with pytest.raises(ValueError, match="Parent unknown must be added"):
        tree.add_segment(child)

    state_after = json.dumps(to_json(tree.segments), sort_keys=True)
    assert state_before == state_after
    assert tree.validate() is True

def test_tree_duplicate_id_atomicity():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    state_before = json.dumps(to_json(tree.segments), sort_keys=True)

    dup = Segment("s0", "s0", Modality.TEXT, ["extract"])
    with pytest.raises(ValueError, match="already exists"):
        tree.add_segment(dup)

    state_after = json.dumps(to_json(tree.segments), sort_keys=True)
    assert state_before == state_after
    assert tree.validate() is True

def test_tree_cycle_atomicity():
    tree = SegmentTree()
    root = Segment("s0", None, Modality.TEXT, ["utf8_decode"])
    tree.add_segment(root)

    child = Segment("s1", "s0", Modality.TEXT, ["extract"])
    tree.add_segment(child)

    state_before = json.dumps(to_json(tree.segments), sort_keys=True)

    # Re-adding s0 under s1 would close the loop s0 -> s1 -> s0
    cycle_seg = Segment("s0", "s1", Modality.TEXT, ["cycle"])
    with pytest.raises(ValueError, match="already exists"):
        tree.add_segment(cycle_seg)

    # A self-parented segment would be a one-node cycle
    self_loop = Segment("s2", "s2", Modality.TEXT, ["cycle"])
    with pytest.raises(ValueError, match="Parent s2 must be added"):
        tree.add_segment(self_loop)

    state_after = json.dumps(to_json(tree.segments), sort_keys=True)
    assert state_before == state_after
    assert tree.root_id == "s0"
    assert tree.segments["s0"].parent_id is None
    assert tree.validate() is True
