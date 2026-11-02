"""Only the approved frozen-profile R1-G operations; no tuning or calibration."""

from litmus.evaluation.run import main

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        from pathlib import Path
        from uuid import uuid4

        from litmus.calibration_run import new_json, now

        new_json(
            Path(__file__).resolve().parents[1]
            / "eval/results/r1g"
            / ("stop." + uuid4().hex + ".json"),
            {
                "status": "STOP",
                "created": now(),
                "type": type(error).__name__,
                "reason": str(error),
            },
        )
        raise
