from typing import Optional, List, Any, Dict
from src.litmus.schemas import Segment, Modality

class SegmentTree:
    def __init__(self):
        self.segments: Dict[str, Segment] = {}
        self.root_id: Optional[str] = None

    def add_segment(self, segment: Segment):
        # Tree validity checks (SPEC 5.1)
        if segment.parent_id is not None:
            if segment.parent_id not in self.segments:
                raise ValueError(f"Parent {segment.parent_id} must be added before child {segment.segment_id}")

        if segment.segment_id in self.segments:
            raise ValueError(f"Segment {segment.segment_id} already exists")

        self.segments[segment.segment_id] = segment
        if segment.parent_id is None:
            if self.root_id is not None:
                raise ValueError("Only one root segment allowed for R1 shapes")
            self.root_id = segment.segment_id

    def get_ancestry(self, segment_id: str) -> List[str]:
        path = []
        curr = segment_id
        while curr is not None:
            path.append(curr)
            curr = self.segments[curr].parent_id
        return path[::-1]

    def validate(self) -> bool:
        if not self.segments:
            return False
        if self.root_id is None:
            return False

        # Check for cycles (acyclic)
        for sid in self.segments:
            visited = set()
            curr = sid
            while curr is not None:
                if curr in visited:
                    return False # Cycle
                visited.add(curr)
                curr = self.segments[curr].parent_id
        return True
