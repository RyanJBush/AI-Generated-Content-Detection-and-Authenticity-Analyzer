"""C2PA provenance support (R1-D; docs/plans/R1-D-PLAN.md).

D1 provides the packaged trust list and settings builder. D2 adds an internal
read/map/rule pipeline with a bounded worker. It is not connected to reports
or the CLI: production analysis stays disabled, with the R0 image placeholder.
"""
