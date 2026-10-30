"""Report assembly; optional text scoring, quality and image provenance."""
import hashlib
import os
from typing import Any, Callable, Dict, List, Optional, Sequence

from litmus import __version__
from litmus.ingestion import Ingested, ingest
from litmus.offline import offline_guards
from litmus.schemas import Modality, OriginEvidence, OriginResult, Segment, to_json
from litmus.tree import SegmentTree

REPORT_SCHEMA = "litmus-report/r0"
PLACEHOLDER_VERSION = "r0-placeholder"

PLACEHOLDER_LIMITATIONS = [
    "R0 placeholder analyzer: no analysis was performed",
    "absence of evidence is not evidence of human origin",
]
REPORT_LIMITATIONS = [
    "R0 skeleton: placeholder analyzers only; no detector and no C2PA analysis",
    "no result in this report is a probability or a verdict",
]
DETECTOR_REPORT_LIMITATIONS = [
    "text origin score is uncalibrated in R1-B1; image analyzers are "
    "placeholders and there is no C2PA analysis",
    "no result in this report is a probability or a verdict",
]
# Appended to the report limitations only when quality observers ran
QUALITY_REPORT_LIMITATIONS = [
    "quality observations do not establish AI origin and never affect origin "
    "results",
    "quality lexicons are English-oriented and provisional (v1)",
    "quality word counts assume space-separated scripts; text without spaces "
    "(e.g. CJK) counts each run as one word",
    "quality counts describe surface patterns, not quality judgments; "
    "frequencies depend on genre",
    "homoglyphs and zero-width or format characters can split words and evade "
    "quality matches",
    "at most 1,000 quality spans are listed per observer; counts are exact",
]
TextOrigin = Callable[[str], OriginEvidence]
_CODEC_STEP = {"utf-8": "utf8_decode", "utf-16-le": "utf16le_decode",
               "utf-16-be": "utf16be_decode"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_origin_placeholder(text: str) -> OriginEvidence:
    if not text.strip():
        # Addendum B2: whitespace-only text is accepted but inconclusive
        reasons = ["no_nonwhitespace_content"]
    else:
        reasons = ["no_text_origin_detector_in_r0"]
    return OriginEvidence(
        method_id="text_origin_placeholder",
        method_version=PLACEHOLDER_VERSION,
        result=OriginResult.INCONCLUSIVE,
        reasons=reasons,
        limitations=list(PLACEHOLDER_LIMITATIONS),
        # A5: nothing was scored
        details={"scored_window": None},
    )


def image_origin_placeholder() -> OriginEvidence:
    return OriginEvidence(
        method_id="image_origin_placeholder",
        method_version=PLACEHOLDER_VERSION,
        result=OriginResult.NOT_SUPPORTED,
        reasons=["c2pa_analyzer_disabled_in_r0", "no_image_detector_in_r0"],
        limitations=list(PLACEHOLDER_LIMITATIONS),
    )


def _root_segment(ing: Ingested, text_origin: Optional[TextOrigin],
                  c2pa_enabled: bool = False) -> Segment:
    if ing.text is not None:
        # Resolved at call time so the placeholder stays the default
        analyze_text = text_origin or text_origin_placeholder
        notes = ["byte order mark removed"] if ing.bom else []
        return Segment(
            segment_id="s0",
            parent_id=None,
            modality=Modality.TEXT,
            derivation=[_CODEC_STEP[ing.encoding]],
            local_frame={"type": "text_codepoints", "length": len(ing.text)},
            content_sha256=_sha256(ing.text.encode("utf-8")),
            extraction={"status": "complete", "notes": notes},
            origin=[analyze_text(ing.text)],
        )
    width, height = ing.image_size
    if c2pa_enabled:
        from litmus.c2pa.analyzer import analyze_image
        origin = analyze_image(ing.raw, ing.mime)
    else:
        origin = image_origin_placeholder()
    return Segment(
        segment_id="s0",
        parent_id=None,
        modality=Modality.IMAGE,
        derivation=["image_decode"],
        local_frame={"type": "pixels", "width": width, "height": height},
        content_sha256=_sha256(ing.raw),
        extraction={"status": "complete", "notes": list(ing.notes)},
        origin=[origin],
    )


def _coverage(ing: Ingested, segments: List[Segment]) -> Dict[str, Any]:
    if not segments:
        return {
            "segments_created": 0,
            "skipped": [{"item": "input", "reason": ing.reason}],
            "unit": None, "total": None, "in_segments": None, "ratio": None,
        }
    if ing.text is not None:
        unit, total = "text_codepoints", len(ing.text)
    else:
        unit, total = "pixels", ing.image_size[0] * ing.image_size[1]
    # R1 shapes: one root segment covering the whole input
    return {
        "segments_created": len(segments),
        "skipped": [],
        "unit": unit, "total": total, "in_segments": total, "ratio": 1.0,
    }


def _input_sha256(ing: Ingested) -> Optional[str]:
    if ing.raw is not None:
        return _sha256(ing.raw)
    if ing.size == 0:
        return _sha256(b"")
    return None  # not read (e.g. over the size limit)


def _add_quality(segment: Segment, text: str, observers: Sequence) -> None:
    """Origin is already computed; observers get only the decoded text."""
    from litmus.quality.observers import observe_all

    segment.quality = observe_all(text, observers)


def build_report(path: str, text_origin: Optional[TextOrigin] = None,
                 quality_observers: Optional[Sequence] = None, *,
                 c2pa_enabled: bool = False) -> Dict[str, Any]:
    """text_origin: analyzer for text segments; None uses the R0 placeholder.
    quality_observers: constructed observers (litmus.quality.observers), run on
    text segments after origin; None (the default) runs none and leaves the
    report exactly as without quality support."""
    ing = ingest(path)

    tree = SegmentTree()
    if ing.accepted:
        root = _root_segment(ing, text_origin, c2pa_enabled)
        if quality_observers is not None and ing.text is not None:
            _add_quality(root, ing.text, quality_observers)
        tree.add_segment(root)
        if not tree.validate():
            raise RuntimeError("internal error: invalid segment tree")
    segments = list(tree.segments.values())
    limitations = list(REPORT_LIMITATIONS if text_origin is None
                       else DETECTOR_REPORT_LIMITATIONS)
    if segments and segments[0].origin[0].method_id == "c2pa_provenance":
        limitations = ["no result in this report is a probability or a verdict",
                       *segments[0].origin[0].limitations]
    if quality_observers is not None:
        limitations += QUALITY_REPORT_LIMITATIONS

    return {
        "report_schema": REPORT_SCHEMA,
        "tool": {"name": "litmus", "version": __version__},
        "input": {
            "file_name": os.path.basename(path),
            "size_bytes": ing.size,
            "sha256": _input_sha256(ing),
            "detected_type": ing.mime,
            "ingestion": {"result": ing.result, "reason": ing.reason},
        },
        "segments": [to_json(s) for s in segments],
        "extraction_coverage": _coverage(ing, segments),
        "limitations": limitations,
    }


def run_analysis(path: str, text_origin: Optional[TextOrigin] = None,
                 quality_observers: Optional[Sequence] = None, *,
                 c2pa_enabled: bool = False) -> Dict[str, Any]:
    """Build a report with the offline guards active for the whole analysis."""
    with offline_guards():
        report = build_report(path, text_origin, quality_observers,
                              c2pa_enabled=c2pa_enabled)
    report["offline"] = {
        "socket_guard": "loopback_only",
        "subprocess_guard": "blocked",
    }
    return report
