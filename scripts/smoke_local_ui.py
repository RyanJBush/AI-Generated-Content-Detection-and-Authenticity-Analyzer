"""Model-free browser test server with constructed timing/error markers.

Not the application launcher. Never use this helper for scientific evaluation.
"""

import time

from litmus.local_ui.server import make_server
from litmus.report import run_analysis


def constructed(path, options):
    from pathlib import Path

    data = Path(path).read_bytes()
    if data.startswith(b"SLOW_UI_FIXTURE"):
        time.sleep(3)
    if data.startswith(b"FAIL_UI_FIXTURE"):
        raise RuntimeError("constructed UI failure")
    if options["text_origin"]:
        raise RuntimeError("constructed missing models; model-free test only")
    observers = None
    if options["quality"]:
        from litmus.quality.observers import build_observers

        observers = build_observers()
    return run_analysis(path, quality_observers=observers)


if __name__ == "__main__":
    server = make_server(8766, analyze=constructed)
    print(server.origin, flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.service.close()
