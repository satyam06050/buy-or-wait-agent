"""Command-line entry point for the Stage 7 full run."""
from __future__ import annotations

import argparse
import sys

from .pipeline import _offline_explanation_transport, run_full_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Buy or Wait? over dataset/requests.csv")
    parser.add_argument("--dataset", default="dataset")
    parser.add_argument("--output", default="output.csv")
    parser.add_argument("--offline-explanations", action="store_true", help="development-only deterministic prose transport")
    args = parser.parse_args()
    try:
        result = run_full_pipeline(
            dataset_dir=args.dataset,
            output_path=args.output,
            explanation_cache_dir=(
                "/tmp/phase7-offline-explanation-cache"
                if args.offline_explanations else "cache/stage6/explanations"
            ),
            call_log_path=(
                "/tmp/phase7-offline-call_log.jsonl"
                if args.offline_explanations else "evaluation/call_log.jsonl"
            ),
            explanation_transport=(
                _offline_explanation_transport if args.offline_explanations else None
            ),
        )
    except Exception as exc:
        print(f"full run failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(result.rows)} validated rows to {result.output_path}")
    if result.stage5.text_errors:
        print(f"text extraction errors: {len(result.stage5.text_errors)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
