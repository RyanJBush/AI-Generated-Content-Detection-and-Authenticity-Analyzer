from typing import Dict, List, Optional

from src.litmus.schemas import Segment


class SegmentTree:
    def __init__(self):
        self.segments: Dict[str, Segment] = {}
        self.root_id: Optional[str] = None

    def add_segment(self, segment: Segment):
        # 1. Validate before mutating
        self._validate_addition(segment)

        # 2. Mutate
        self.segments[segment.segment_id] = segment
        if segment.parent_id is None:
            self.root_id = segment.segment_id

    def _validate_addition(self, segment: Segment):
        # Second root
        if segment.parent_id is None and self.root_id is not None:
            raise ValueError("Only one root segment allowed for R1 shapes")

        # Duplicate ID
        if segment.segment_id in self.segments:
            raise ValueError(f"Segment {segment.segment_id} already exists")

        # Unknown parent
        if segment.parent_id is not None and segment.parent_id not in self.segments:
            raise ValueError(
                f"Parent {segment.parent_id} must be added before child {segment.segment_id}"
            )

        # Cycle detection
        curr = segment.parent_id
        while curr is not None:
            if curr == segment.segment_id:
                raise ValueError(f"Cycle detected at {segment.segment_id}")
            curr = self.segments[curr].parent_id if curr in self.segments else None

    def get_ancestry(self, segment_id: str) -> List[str]:
        path = []
        curr = segment_id
        while curr is not None:
            path.append(curr)
            curr = self.segments[curr].parent_id if curr in self.segments else None
        return path[::-1]

    def validate(self) -> bool:
        if not self.segments:
            return False
        if self.root_id is None:
            return False

        # Cycle detection
        for sid in self.segments:
            visited = set()
            curr = sid
            while curr is not None:
                if curr in visited:
                    return False # Cycle
                visited.add(curr)
                curr = self.segments[curr].parent_id if curr in self.segments else None
        return True
