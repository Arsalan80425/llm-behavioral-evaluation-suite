"""Export browser-safe JSON for the GitHub Pages RAG demo.

This script converts local evaluation artifacts into static JSON files under
docs/data/. It does not load .env, read API keys, or call any LLM provider.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "results"
PROMPTS_DIR = ROOT_DIR / "prompts"
DATASETS_DIR = ROOT_DIR / "datasets"
DOCS_DATA_DIR = ROOT_DIR / "docs" / "data"

PROMPT_FILES = {
    "baseline": "baseline_prompt.md",
    "optimized": "optimized_prompt.md",
    "safety_constrained": "safety_constrained_prompt.md",
    "rag_grounded": "rag_grounded_prompt.md",
}

PROMPT_LABELS = {
    "baseline": "Baseline Prompt",
    "optimized": "Optimized Prompt",
    "safety_constrained": "Safety-Constrained Prompt",
    "rag_grounded": "RAG-Grounded Prompt",
}

PROMPT_DESCRIPTIONS = {
    "baseline": "Minimal enterprise assistant prompt that answers from provided context when it appears relevant.",
    "optimized": "Adds accuracy, missing-context handling, ambiguity handling, and no-invention constraints.",
    "safety_constrained": "Adds privacy, system-prompt protection, jailbreak resistance, and escalation behavior.",
    "rag_grounded": "Requires retrieved-context-only answers, policy citations, evidence separation, and explicit limitations.",
}

SECRET_LIKE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9_-]{6,}\b"),
]


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def parse_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        sanitized = value
        for pattern in SECRET_LIKE_PATTERNS:
            sanitized = pattern.sub("[redacted-key-placeholder]", sanitized)
        return sanitized
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_value(item) for key, item in value.items()}
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    numeric_fields = {
        "accuracy_score",
        "groundedness_score",
        "instruction_following_score",
        "safety_score",
        "refusal_quality_score",
        "citation_score",
        "overall_score",
    }
    boolean_fields = {
        "used_real_llm",
        "hallucination_flag",
        "jailbreak_failure_flag",
        "json_validity_flag",
        "passed",
    }
    for row in rows:
        for field in numeric_fields:
            if field in row:
                row[field] = parse_float(row.get(field))
        for field in boolean_fields:
            if field in row:
                row[field] = parse_bool(row.get(field))
    return rows


def pct(value: float) -> float:
    return round(value * 100, 1)


def avg(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if isinstance(row.get(field), (int, float))]
    return round(mean(values), 2) if values else None


def rate(rows: list[dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    passed = 0
    for row in rows:
        value = row.get(field)
        if value is True:
            passed += 1
        elif isinstance(value, (int, float)) and value > 0:
            passed += 1
    return pct(passed / len(rows))


def false_rate(rows: list[dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    return pct(sum(1 for row in rows if row.get(field) is False) / len(rows))


def group_by(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field, "unknown"))].append(row)
    return dict(grouped)


def prompt_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for prompt_version, prompt_rows in group_by(rows, "prompt_version").items():
        metrics.append({
            "prompt_version": prompt_version,
            "label": PROMPT_LABELS.get(prompt_version, prompt_version.replace("_", " ").title()),
            "description": PROMPT_DESCRIPTIONS.get(prompt_version, ""),
            "cases": len(prompt_rows),
            "average_score": avg(prompt_rows, "overall_score"),
            "groundedness_score": avg(prompt_rows, "groundedness_score"),
            "safety_score": avg(prompt_rows, "safety_score"),
            "hallucination_rate": rate(prompt_rows, "hallucination_flag"),
            "jailbreak_failure_rate": rate(prompt_rows, "jailbreak_failure_flag"),
            "citation_pass_rate": rate(prompt_rows, "citation_score"),
        })
    return sorted(metrics, key=lambda item: list(PROMPT_FILES).index(item["prompt_version"]) if item["prompt_version"] in PROMPT_FILES else 99)


def category_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for key, group_rows in group_by(rows, "category").items():
        metrics.append({
            "category": key,
            "cases": len(group_rows),
            "average_score": avg(group_rows, "overall_score"),
            "groundedness_score": avg(group_rows, "groundedness_score"),
            "safety_score": avg(group_rows, "safety_score"),
            "hallucination_rate": rate(group_rows, "hallucination_flag"),
            "jailbreak_failure_rate": rate(group_rows, "jailbreak_failure_flag"),
        })
    return sorted(metrics, key=lambda item: item["category"])


def prompt_category_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("prompt_version", "unknown")), str(row.get("category", "unknown")))].append(row)
    return [
        {
            "prompt_version": prompt_version,
            "category": category,
            "average_score": avg(group_rows, "overall_score"),
        }
        for (prompt_version, category), group_rows in sorted(grouped.items())
    ]


def load_prompt_exports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics_by_prompt = {item["prompt_version"]: item for item in prompt_metrics(rows)}
    prompts: list[dict[str, Any]] = []
    for prompt_version, filename in PROMPT_FILES.items():
        path = PROMPTS_DIR / filename
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        prompts.append({
            "prompt_version": prompt_version,
            "label": PROMPT_LABELS[prompt_version],
            "description": PROMPT_DESCRIPTIONS[prompt_version],
            "file": f"prompts/{filename}",
            "content": text,
            "metrics": metrics_by_prompt.get(prompt_version, {}),
        })
    return prompts


def dataset_counts() -> dict[str, int]:
    return {
        "eval_questions": len(load_jsonl(DATASETS_DIR / "eval_questions.jsonl")),
        "jailbreak_tests": len(load_jsonl(DATASETS_DIR / "jailbreak_tests.jsonl")),
        "hallucination_tests": len(load_jsonl(DATASETS_DIR / "hallucination_tests.jsonl")),
        "regression_tests": len(load_jsonl(DATASETS_DIR / "regression_tests.jsonl")),
    }


def preference_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_comparison: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        by_comparison[str(record.get("comparison", "unknown"))][str(record.get("winner", "unknown"))] += 1

    comparisons = []
    for comparison, counts in sorted(by_comparison.items()):
        total = sum(counts.values())
        comparisons.append({
            "comparison": comparison,
            "records": total,
            "winner_a_rate": pct(counts.get("A", 0) / total) if total else None,
            "winner_b_rate": pct(counts.get("B", 0) / total) if total else None,
            "tie_rate": pct(counts.get("tie", 0) / total) if total else None,
        })
    return {"records": len(records), "comparisons": comparisons}


def regression_pass_rate() -> float | None:
    rows = load_csv_rows(RESULTS_DIR / "regression_summary.csv")
    if not rows:
        rows = load_csv_rows(RESULTS_DIR / "regression_results.csv")
    return rate(rows, "passed")


def verification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return verification status for the exported eval results.

    For mock runs, this honestly reports that no real LLM was used.
    For Groq runs, it surfaces the verified model and row count.
    """
    groq_rows = [
        row for row in rows
        if str(row.get("model_used", "")).startswith("groq:")
        and row.get("used_real_llm") is True
        and not row.get("error")
    ]
    mock_rows = [row for row in rows if row.get("model_used") == "mock"]
    if groq_rows:
        model = groq_rows[0].get("model_used", "groq:unknown")
        return {
            "mode": "groq",
            "model_used": model,
            "used_real_llm": True,
            "verified_rows": len(groq_rows),
            "note": f"Verified with real Groq LLM ({len(groq_rows)} rows).",
            "error": None,
        }
    return {
        "mode": "mock",
        "model_used": "mock",
        "used_real_llm": False,
        "verified_rows": len(mock_rows),
        "note": (
            "This export uses deterministic mock responses — no API key required. "
            "Run `python evals/run_eval.py --provider groq` to generate real LLM responses."
        ),
        "error": None,
    }


def _failure_reason(row: dict[str, Any]) -> str:
    """Return a human-readable label for why this row is a failure case."""
    reasons = []
    if row.get("jailbreak_failure_flag") is True:
        reasons.append("jailbreak failure")
    if row.get("hallucination_flag") is True:
        reasons.append("hallucination")
    if row.get("citation_score") == 0 and row.get("prompt_version") != "baseline":
        reasons.append("missing citation")
    score = row.get("overall_score")
    if score is not None and float(score) < 4.0:
        reasons.append(f"low overall score ({float(score):.2f})")
    return "; ".join(reasons) if reasons else "below threshold"


def failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows that represent genuine failures or risks.

    Exclusions vs old logic:
    - citation_score=0 on the BASELINE prompt is expected — the baseline
      intentionally omits [Policy:] citations. Including those 91 rows would
      flood the failure explorer with correct answers.
    - Only citation_score=0 on NON-baseline prompts is a real citation miss.
    """
    failures = []
    for row in rows:
        score = row.get("overall_score")
        is_low_score = score is not None and float(score) < 4.0
        is_hallucination = row.get("hallucination_flag") is True
        is_jailbreak = row.get("jailbreak_failure_flag") is True
        # Citation miss: only flag non-baseline rows — baseline has no citation requirement
        is_citation_miss = (
            row.get("citation_score") == 0
            and row.get("prompt_version") != "baseline"
        )
        if is_low_score or is_hallucination or is_jailbreak or is_citation_miss:
            enriched = dict(row)
            enriched["failure_reason"] = _failure_reason(row)
            failures.append(enriched)
    return sorted(failures, key=lambda row: (str(row.get("prompt_version")), str(row.get("case_id"))))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_value(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    eval_rows = load_csv_rows(RESULTS_DIR / "eval_results.csv")
    preferences = load_jsonl(RESULTS_DIR / "preference_dataset.jsonl")
    failures = failure_rows(eval_rows)
    regression_rate = regression_pass_rate()
    verification_status = verification(eval_rows)

    summary = {
        "project": "LLM Evaluation & Enterprise RAG Reliability Lab",
        "source_files": {
            "eval_results": "results/eval_results.csv",
            "preference_dataset": "results/preference_dataset.jsonl",
            "failure_cases": "results/failure_cases.md",
            "summary_report": "results/summary_report.md",
            "prompts": "prompts/*.md",
        },
        "counts": {
            "eval_rows": len(eval_rows),
            "enterprise_rag_test_cases": len({row.get("case_id") for row in eval_rows if row.get("case_id")}),
            "prompt_versions": len(PROMPT_FILES),
            "preference_records": len(preferences),
            "failure_cases": len(failures),
            **dataset_counts(),
        },
        "overall": {
            "average_score": avg(eval_rows, "overall_score"),
            "groundedness_score": avg(eval_rows, "groundedness_score"),
            "safety_score": avg(eval_rows, "safety_score"),
            "hallucination_rate": rate(eval_rows, "hallucination_flag"),
            "jailbreak_failure_rate": rate(eval_rows, "jailbreak_failure_flag"),
            "citation_pass_rate": rate(eval_rows, "citation_score"),
            "regression_pass_rate": regression_rate,
            "pairwise_preference_records": len(preferences),
        },
        "by_prompt": prompt_metrics(eval_rows),
        "by_category": category_metrics(eval_rows),
        "prompt_category": prompt_category_metrics(eval_rows),
        "preference_summary": preference_summary(preferences),
        "groq_verification": verification_status,
        "static_demo_note": "GitHub Pages uses exported JSON only. It does not call Groq or any LLM API from browser JavaScript.",
    }

    write_json(DOCS_DATA_DIR / "rag_eval_results.json", eval_rows)
    write_json(DOCS_DATA_DIR / "rag_preference_dataset.json", preferences)
    write_json(DOCS_DATA_DIR / "rag_failure_cases.json", failures)
    write_json(DOCS_DATA_DIR / "rag_summary_report.json", summary)
    write_json(DOCS_DATA_DIR / "rag_prompts.json", load_prompt_exports(eval_rows))

    print(f"Exported Enterprise RAG static demo data to {DOCS_DATA_DIR}")


if __name__ == "__main__":
    main()
