"""User-facing failures that prevent creation of a valid report."""


class C2paUnavailable(RuntimeError):
    """Requested image provenance cannot be initialized safely."""
