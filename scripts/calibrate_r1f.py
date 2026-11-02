"""Run only explicitly approved local R1-F development operations."""

from pathlib import Path

from litmus.calibration_run import main, new_json, now

if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        # Append failure evidence without modifying source, prior results or inputs.
        import sys

        if not isinstance(error, SystemExit) or error.code:
            destination = Path(__file__).resolve().parents[1] / "eval/results/r1f"
            import uuid

            new_json(
                destination / ("failure." + uuid.uuid4().hex + ".json"),
                {
                    "status": "STOP",
                    "error": type(error).__name__ + ":" + str(error),
                    "created": now(),
                    "arguments": sys.argv[1:],
                    "test_scoring_authorized": False,
                },
            )
        raise
