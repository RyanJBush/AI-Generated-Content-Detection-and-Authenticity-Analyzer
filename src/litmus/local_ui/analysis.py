"""Use existing analyzers without changing their defaults or identities."""


class Analyzers:
    """One lazy production model pair owned by the single UI worker.

    Reuse avoids initializing CUDA again after its frozen startup profile has
    been established. No numerical setting is reapplied.
    """

    def __init__(self):
        self.origin = self.observers = None

    def __call__(self, path, options):
        from litmus.report import run_analysis

        if options["text_origin"] and self.origin is None:
            from litmus.scorer.analyzer import BinocularsAnalyzer

            self.origin = BinocularsAnalyzer(device="cuda")
        if options["quality"] and self.observers is None:
            from litmus.quality.observers import build_observers

            self.observers = build_observers()
        return run_analysis(
            path,
            self.origin if options["text_origin"] else None,
            self.observers if options["quality"] else None,
            c2pa_enabled=options["c2pa"],
        )

    def close(self):
        self.origin = self.observers = None
