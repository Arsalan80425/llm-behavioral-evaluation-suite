"""Run jailbreak and prompt-injection safety tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from evals.run_eval import run_cases
    from evals.utils import DATASETS_DIR, RESULTS_DIR, append_section, ensure_results_dir, load_jsonl
else:
    from .run_eval import run_cases
    from .utils import DATASETS_DIR, RESULTS_DIR, append_section, ensure_results_dir, load_jsonl


def write_safety_report(df: pd.DataFrame) -> None:
    """Write safety-test summary to the main report."""
    lines = [
        "Jailbreak and prompt-injection tests evaluate whether prompts resist malicious instructions, sensitive-data exposure, and policy invention.",
        "",
        "| Prompt Version | Cases | Avg Safety | Jailbreak Failure Rate |",
        "|---|---:|---:|---:|",
    ]
    for prompt_version, group in df.groupby("prompt_version"):
        lines.append(f"| {prompt_version} | {len(group)} | {group['safety_score'].mean():.2f} | {group['jailbreak_failure_flag'].mean():.1%} |")
    append_section(RESULTS_DIR / "summary_report.md", "Safety Test Summary", "\n".join(lines))


def main() -> None:
    ensure_results_dir()
    cases = load_jsonl(DATASETS_DIR / "jailbreak_tests.jsonl")
    df = pd.DataFrame(run_cases(cases, dataset_name="jailbreak_tests"))
    df.to_csv(RESULTS_DIR / "safety_results.csv", index=False)
    write_safety_report(df)
    print(f"Safety test rows: {len(df)}")
    print(f"Jailbreak failure rate: {df['jailbreak_failure_flag'].mean():.1%}")


if __name__ == "__main__":
    main()
