"""Local Gradio UI for Litmus (Block 5, local only; no Hugging Face deployment).

Uses the same scorer, report, identity and calibration lookup as the CLI (litmus.cli.Analyzer).
Models are loaded lazily on the first analysis, never while building the interface.
Usage: .venv\\Scripts\\python.exe app\\app.py [--pair 0.5b] [--device auto|cuda|cpu] [--dtype float32]
"""
import argparse
import itertools

import gradio as gr

from litmus import config
from litmus.cli import Analyzer
from litmus.report import DISCLAIMER, NOTE, report_to_json
from litmus.scoring import DTYPES, load_pair

FEATURE_LABELS = {
    "stock_phrases": "stock phrase",
    "hedges": "hedge",
    "repeated_ngrams": "repeated 3-gram",
    "inspect_phrases": "phrase to inspect",
}


def lazy_report_fn(pair=config.DEFAULT_PAIR, device="auto", dtype="float32", load=load_pair):
    """report(text) -> report dict; loads the model pair on first call only."""
    analyzer = None

    def report(text):
        nonlocal analyzer
        if analyzer is None:
            analyzer = Analyzer(load(pair, device=device, dtype=dtype))
        return analyzer.report(text)

    return report


def highlight_segments(text, report):
    """Split the original text into (segment, label) pairs; overlapping features share a combined label."""
    features = report["slop"]["features"]
    bounds = {0, len(text)}
    for feature in features.values():
        for start, end in feature["spans"]:
            bounds.update((start, end))
    points = sorted(bounds)
    segments = []
    for start, end in itertools.pairwise(points):
        labels = [
            FEATURE_LABELS[name]
            for name, feature in features.items()
            if any(s <= start and end <= e for s, e in feature["spans"])
        ]
        segments.append((text[start:end], " + ".join(labels) or None))
    return segments


def summary_markdown(report):
    b = report["binoculars"]
    lines = []
    if b["flag"] is None:
        lines.append(f"**Scoring failed:** {b['error']}")
    elif b["flag"] == "too_short":
        lines.append(f"**Not scored:** {b['flag_text']} ({report['n_tokens']} tokens).")
    else:
        lines.append(f"**Binoculars score (B):** {b['score']:.4f}  ·  NLL performer {b['nll_performer']:.4f}  ·  "
                     f"cross-entropy {b['xent']:.4f}  ·  NLL observer {b['baselines']['nll_observer']:.4f}")
        if b["flag"] == "no_calibration":
            lines.append(f"**No flag shown:** {b['calibration_status']['reason']}.")
        else:
            lines.append(f"**Flag:** {b['flag']} ({b['flag_text']}; t_strict {b['calibration']['t_strict']:.4f}, "
                         f"t_primary {b['calibration']['t_primary']:.4f}).")
    lines.append(f"Tokens: {report['n_input_tokens']} input, {report['n_scored_tokens']} scored"
                 + (" (truncated to the first 512)" if report["truncated"] else "") + ".")
    counts = ", ".join(
        f"{FEATURE_LABELS[name]}: {f['count']}" for name, f in report["slop"]["features"].items()
    )
    lines.append(f"Pattern counts (unvalidated heuristic): {counts}.")
    lines.append(f"_{NOTE}_")
    lines.append(f"_{DISCLAIMER}_")
    return "\n\n".join(lines)


def run_analysis(text, report_fn):
    report = report_fn(text)
    return summary_markdown(report), highlight_segments(text, report), report_to_json(report)


def build_app(report_fn):
    with gr.Blocks(title="Litmus") as demo:
        gr.Markdown("# Litmus\nBinoculars likelihood score and slop-pattern report for English text.\n\n"
                    f"_{NOTE}_\n\n_{DISCLAIMER}_")
        text = gr.Textbox(label="Text", lines=12, placeholder="Paste at least 64 tokens of English text.")
        button = gr.Button("Analyze")
        summary = gr.Markdown()
        highlights = gr.HighlightedText(label="Patterns (original text)", combine_adjacent=False, show_legend=True)
        raw = gr.Code(label="Report JSON", language="json")
        button.click(fn=lambda t: run_analysis(t, report_fn), inputs=text, outputs=[summary, highlights, raw])
    return demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=sorted(config.PAIRS), default=config.DEFAULT_PAIR)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--dtype", choices=sorted(DTYPES), default="float32")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    demo = build_app(lazy_report_fn(args.pair, args.device, args.dtype))
    demo.launch(server_name="127.0.0.1", server_port=args.port, share=False)


if __name__ == "__main__":
    main()
