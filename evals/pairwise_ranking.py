"""Generate RLHF-style pairwise preference data from evaluation results."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from evals.run_eval import run_evaluation
    from evals.utils import RESULTS_DIR, ensure_results_dir, write_jsonl
else:
    from .run_eval import run_evaluation
    from .utils import RESULTS_DIR, ensure_results_dir, write_jsonl


COMPARISONS = [
    ("baseline", "optimized"),
    ("optimized", "safety_constrained"),
    ("safety_constrained", "rag_grounded"),
]


def _winner(score_a: float, score_b: float) -> str:
    if abs(score_a - score_b) < 0.05:
        return "tie"
    return "A" if score_a > score_b else "B"


def _rationale(row_a: pd.Series, row_b: pd.Series, winner: str) -> str:
    if winner == "tie":
        return "Responses performed equivalently on the rubric metrics."
    winning = row_a if winner == "A" else row_b
    losing = row_b if winner == "A" else row_a
    reasons = []
    for metric in ["groundedness_score", "safety_score", "citation_score", "instruction_following_score"]:
        if float(winning[metric]) > float(losing[metric]):
            reasons.append(metric.replace("_", " "))
    if not reasons:
        reasons.append(
            f"overall score ({float(winning['overall_score']):.2f} vs {float(losing['overall_score']):.2f})"
        )
    return f"Selected because it had better {', '.join(reasons[:3])}."



def build_preference_dataset(df: pd.DataFrame) -> list[dict]:
    """Build pairwise preference records for configured prompt comparisons."""
    records: list[dict] = []
    for case_id, group in df.groupby("case_id"):
        by_prompt = {row["prompt_version"]: row for _, row in group.iterrows()}
        for prompt_a, prompt_b in COMPARISONS:
            if prompt_a not in by_prompt or prompt_b not in by_prompt:
                continue
            row_a = by_prompt[prompt_a]
            row_b = by_prompt[prompt_b]
            score_a = float(row_a["overall_score"])
            score_b = float(row_b["overall_score"])
            winner = _winner(score_a, score_b)
            records.append({
                "case_id": case_id,
                "question": row_a["question"],
                "comparison": f"{prompt_a}_vs_{prompt_b}",
                "response_a": row_a["response"],
                "response_b": row_b["response"],
                "winner": winner,
                "rationale": _rationale(row_a, row_b, winner),
                "scores": {
                    "response_a_overall": score_a,
                    "response_b_overall": score_b,
                },
            })
    return records


def main() -> None:
    ensure_results_dir()
    results_path = RESULTS_DIR / "eval_results.csv"
    if results_path.exists():
        df = pd.read_csv(results_path)
    else:
        df = run_evaluation()

    records = build_preference_dataset(df)
    output_path = RESULTS_DIR / "preference_dataset.jsonl"
    write_jsonl(output_path, records)

    win_summary = pd.DataFrame(records)
    if not win_summary.empty:
        summary = win_summary.groupby(["comparison", "winner"]).size().unstack(fill_value=0)
        summary.to_csv(RESULTS_DIR / "pairwise_summary.csv")

    print(f"Wrote {len(records)} preference records to {output_path}")


if __name__ == "__main__":
    main()
