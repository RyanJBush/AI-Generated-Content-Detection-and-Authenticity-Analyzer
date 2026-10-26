# SUPERSEDED: first fp32 0.5B benchmark run (2026-10-26 13:55 -04:00)

Status: **superseded** by `eval/results/benchmark_0.5b_float32.json` (run at 13:56 -04:00). Preserved unedited.

This run completed with exit code 0 using the production scorer, but two measurement defects were found in the
script version that produced it (never committed in that form):

1. `host_peak_working_set_bytes` is `null`: the Windows `GetProcessMemoryInfo` call passed the process pseudo-handle
   without ctypes `argtypes`/`restype`, so the call failed and returned None.
2. `max_memory_reserved_bytes` per length includes cached allocator blocks from earlier lengths
   (no `torch.cuda.empty_cache()` before `reset_peak_memory_stats()`), so it is not a per-length peak.

The committed `eval/benchmark.py` differs from the producing version only by those two fixes. Timings,
`max_memory_allocated_bytes` and pilot statistics are not affected by either defect; the pilot statistics are
identical to the superseding run.
