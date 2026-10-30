"""Minimal unsigned metadata from ingested bytes; never origin evidence."""
import io

from PIL import Image

LABEL = "unverifiable; editable; not evidence"
EXIF_FIELDS = {305: "Software", 271: "Make", 272: "Model", 306: "DateTime"}


def summarize(data: bytes) -> dict:
    result = {
        "label": LABEL, "status": "unavailable", "notes": [],
        "exif": {"status": "unavailable", "tag_count": None, "fields": {}},
        "xmp": {"status": "unavailable", "byte_length": None},
    }
    try:
        with io.BytesIO(data) as stream, Image.open(stream) as image:
            # Inspect components independently so a malformed EXIF block does
            # not hide a readable XMP presence/length, or vice versa.
            try:
                exif = image.getexif()
                result["exif"] = {
                    "status": "present" if exif else "absent",
                    "tag_count": len(exif),
                    "fields": {name: str(exif[tag])[:256]
                               for tag, name in EXIF_FIELDS.items() if tag in exif},
                }
            except Exception as exc:
                result["notes"].append(f"exif_unavailable:{type(exc).__name__}")
            try:
                xmp = image.info.get("xmp")
                if isinstance(xmp, (bytes, str)):
                    encoded = xmp.encode("utf-8") if isinstance(xmp, str) else xmp
                    result["xmp"] = {"status": "present", "byte_length": len(encoded)}
                elif xmp is None:
                    result["xmp"] = {"status": "absent", "byte_length": 0}
                else:
                    result["notes"].append("xmp_unavailable:unexpected_type")
            except Exception as exc:
                result["notes"].append(f"xmp_unavailable:{type(exc).__name__}")
        result["status"] = "partial" if result["notes"] else "examined"
    except Exception as exc:
        result["notes"].append(f"metadata_unavailable:{type(exc).__name__}")
    return result
