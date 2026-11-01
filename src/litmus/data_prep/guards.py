"""Fresh-process preparation guard: no weights, scoring imports or network."""

import builtins
import contextlib
import io
import os
import socket
import sys

from litmus.data_prep.acquisition import PrepError
from litmus.offline import offline_guards

FORBIDDEN = (
    "torch",
    "tensorflow",
    "litmus.scorer.loader",
    "litmus.scorer.analyzer",
    "litmus.scorer.binoculars",
)


@contextlib.contextmanager
def preparation_guards():
    if any(m == p or m.startswith(p + ".") for m in sys.modules for p in FORBIDDEN):
        raise PrepError("model_or_scorer_module_already_loaded")
    saved_open, saved_io, saved_os = builtins.open, io.open, os.open
    saved_import, saved_connect = builtins.__import__, socket.socket.connect
    attempts = {"weight_file_access": 0, "forbidden_import": 0, "connections": 0}

    def checked_path(path):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(path).lower()
            if name.endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt")):
                attempts["weight_file_access"] += 1
                raise PrepError("model_weight_file_access_forbidden")

    def wrap(original):
        def guarded(path, *args, **kwargs):
            checked_path(path)
            return original(path, *args, **kwargs)

        return guarded

    def guarded_import(name, *args, **kwargs):
        if any(name == p or name.startswith(p + ".") for p in FORBIDDEN):
            attempts["forbidden_import"] += 1
            raise PrepError("model_or_scoring_import_forbidden")
        return saved_import(name, *args, **kwargs)

    def no_connection(*args, **kwargs):
        attempts["connections"] += 1
        raise PrepError("preparation_network_forbidden")

    os.environ["USE_TORCH"], os.environ["USE_TF"] = "0", "0"
    try:
        with offline_guards():
            builtins.open, io.open, os.open = (
                wrap(saved_open),
                wrap(saved_io),
                wrap(saved_os),
            )
            builtins.__import__ = guarded_import
            socket.socket.connect = no_connection
            yield attempts
            if any(
                m == p or m.startswith(p + ".") for m in sys.modules for p in FORBIDDEN
            ):
                raise PrepError("model_or_scoring_module_loaded")
    finally:
        builtins.open, io.open, os.open = saved_open, saved_io, saved_os
        builtins.__import__ = saved_import
        socket.socket.connect = saved_connect
