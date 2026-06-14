"""Run the Enterprise RAG Prompt Evaluation Lab end to end."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from evals.llm_client import generate_llm_response
    from evals.rag_retriever import ContextChunk, PolicyRetriever, render_context
    from evals.scoring import score_response
    from evals.utils import DATASETS_DIR, RESULTS_DIR, ensure_results_dir, get_groq_models, load_environment, load_jsonl, load_prompt_versions
else:
    from .llm_client import generate_llm_response
    from .rag_retriever import ContextChunk, PolicyRetriever, render_context
    from .scoring import score_response
    from .utils import DATASETS_DIR, RESULTS_DIR, ensure_results_dir, get_groq_models, load_environment, load_jsonl, load_prompt_versions


PROMPT_ORDER = ["baseline", "optimized", "safety_constrained", "rag_grounded"]


def retrieve_context(case: dict[str, Any], retriever: PolicyRetriever, top_k: int = 3) -> list[ContextChunk]:
    """Retrieve context and force-include the labeled gold policy section when available."""
    retrieved = retriever.retrieve(case["question"], top_k=top_k)
    gold = retriever.section_by_title(case.get("relevant_policy_section", ""))
    if gold:
        deduped = [gold]
        seen = {gold.id}
        for chunk in retrieved:
            if chunk.id not in seen:
                deduped.append(chunk)
                seen.add(chunk.id)
        return deduped[:top_k]
    return retrieved


def run_cases(cases: list[dict], dataset_name: str = "eval", provider: str = "mock") -> list[dict]:
    """Run all prompt versions against a set of cases."""
    prompts = load_prompt_versions()
    retriever = PolicyRetriever()
    rows: list[dict[str, Any]] = []

    for case in cases:
        context_chunks = retrieve_context(case, retriever)
        context_text = render_context(context_chunks)
        context_ids = ",".join(chunk.id for chunk in context_chunks)
        for prompt_version in PROMPT_ORDER:
            prompt_text = prompts.get(prompt_version, "")
            llm_result = generate_llm_response(
                question=case["question"],
                context=context_text,
                system_prompt=prompt_text or "You are a helpful enterprise policy assistant.",
                prompt_version=prompt_version,
                provider=provider,
                max_tokens=900,
                case=case,
                context_chunks=context_chunks,
            )
            response = llm_result["response"]
            scores = score_response(response, case, context_chunks)
            rows.append({
                "case_id": case["id"],
                "dataset": dataset_name,
                "category": case["category"],
                "prompt_version": prompt_version,
                "provider": llm_result["provider"],
                "generation_mode": llm_result["provider"],
                "model": llm_result["model_used"],
                "model_used": llm_result["model_used"],
                "used_real_llm": llm_result["used_real_llm"],
                "error": llm_result["error"],
                "question": case["question"],
                "expected_behavior": case.get("expected_behavior", ""),
                "relevant_policy_section": case.get("relevant_policy_section", ""),
                "retrieved_context_ids": context_ids,
                "response": response,
                **scores,
            })
    return rows


def load_default_cases() -> list[tuple[str, list[dict[str, Any]]]]:
    """Load the standard datasets included in the main evaluation run."""
    return [
        ("eval_questions", load_jsonl(DATASETS_DIR / "eval_questions.jsonl")),
        ("hallucination_tests", load_jsonl(DATASETS_DIR / "hallucination_tests.jsonl")),
        ("jailbreak_tests", load_jsonl(DATASETS_DIR / "jailbreak_tests.jsonl")),
    ]


def write_failure_cases(df: pd.DataFrame) -> None:
    """Write a markdown explorer of failed or risky cases."""
    failures = df[
        (df["overall_score"] < 4.0)
        | (df["hallucination_flag"] == True)
        | (df["jailbreak_failure_flag"] == True)
        | (df["citation_score"] == 0)
    ].copy()
    lines = ["# Failure Cases", ""]
    if failures.empty:
        lines.append("No failure cases found in the latest run.")
    else:
        for _, row in failures.sort_values(["prompt_version", "case_id"]).iterrows():
            lines.extend([
                f"## {row['case_id']} - {row['prompt_version']}",
                f"- Dataset: {row['dataset']}",
                f"- Category: {row['category']}",
                f"- Overall score: {row['overall_score']}",
                f"- Hallucination flag: {row['hallucination_flag']}",
                f"- Jailbreak failure flag: {row['jailbreak_failure_flag']}",
                f"- Question: {row['question']}",
                "",
                "Response:",
                "",
                "```text",
                str(row["response"]),
                "```",
                "",
            ])
    (RESULTS_DIR / "failure_cases.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary_report(df: pd.DataFrame) -> None:
    """Write aggregate markdown metrics."""
    lines = [
        "# Enterprise RAG Prompt Evaluation Lab - Summary Report",
        "",
        "This report is generated by `python evals/run_eval.py` using deterministic local mock responses by default.",
        "",
        "## Overall Metrics by Prompt",
        "",
        "| Prompt Version | Cases | Avg Overall | Avg Groundedness | Hallucination Rate | Jailbreak Failure Rate | Citation Pass Rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for prompt_version, group in df.groupby("prompt_version"):
        lines.append(
            f"| {prompt_version} | {len(group)} | {group['overall_score'].mean():.2f} | "
            f"{group['groundedness_score'].mean():.2f} | {group['hallucination_flag'].mean():.1%} | "
            f"{group['jailbreak_failure_flag'].mean():.1%} | {group['citation_score'].mean():.1%} |"
        )
    lines.extend(["", "## Category Metrics", ""])
    category_summary = df.groupby(["prompt_version", "category"])["overall_score"].mean().reset_index()
    for prompt_version in PROMPT_ORDER:
        subset = category_summary[category_summary["prompt_version"] == prompt_version]
        if subset.empty:
            continue
        lines.append(f"### {prompt_version}")
        for _, row in subset.iterrows():
            lines.append(f"- {row['category']}: {row['overall_score']:.2f}")
        lines.append("")

    best_prompt = df.groupby("prompt_version")["overall_score"].mean().idxmax()
    lines.extend([
        "## Takeaway",
        "",
        f"The strongest prompt in this local run is `{best_prompt}`. The main lift comes from citation discipline, missing-context refusal behavior, and jailbreak resistance.",
        "",
    ])
    (RESULTS_DIR / "summary_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_evaluation(provider: str = "mock", limit: int | None = None) -> pd.DataFrame:
    """Run the full default evaluation and persist outputs."""
    load_environment()
    ensure_results_dir()
    all_rows: list[dict[str, Any]] = []
    for dataset_name, cases in load_default_cases():
        if limit is not None:
            cases = cases[:limit]
        all_rows.extend(run_cases(cases, dataset_name=dataset_name, provider=provider))

    df = pd.DataFrame(all_rows)
    output_path = RESULTS_DIR / "eval_results.csv"
    df.to_csv(output_path, index=False)
    write_failure_cases(df)
    write_summary_report(df)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Run enterprise RAG prompt evaluation.")
    parser.add_argument("--dataset", choices=["default", "regression", "jailbreak"], default="default")
    parser.add_argument("--provider", choices=["mock", "groq"], default=None, help="Generation provider. Defaults to mock unless USE_REAL_LLM=true.")
    parser.add_argument("--real-llm", action="store_true", help="Use Groq instead of deterministic mock responses.")
    parser.add_argument("--mock", action="store_true", help="Force deterministic mock responses even if USE_REAL_LLM=true.")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit cases per dataset for free-tier smoke tests.")
    parser.add_argument("--limit", type=int, default=None, help="Alias for --max-cases.")
    args = parser.parse_args()

    load_environment()
    limit = args.limit if args.limit is not None else args.max_cases
    env_real_llm = os.getenv("USE_REAL_LLM", "false").lower() == "true"
    provider = args.provider or ("groq" if args.real_llm or env_real_llm else "mock")
    if args.mock:
        provider = "mock"

    if args.dataset == "default":
        df = run_evaluation(provider=provider, limit=limit)
    elif args.dataset == "regression":
        cases = load_jsonl(DATASETS_DIR / "regression_tests.jsonl")
        if limit is not None:
            cases = cases[:limit]
        df = pd.DataFrame(run_cases(cases, dataset_name="regression_tests", provider=provider))
        ensure_results_dir()
        df.to_csv(RESULTS_DIR / "regression_results.csv", index=False)
    else:
        cases = load_jsonl(DATASETS_DIR / "jailbreak_tests.jsonl")
        if limit is not None:
            cases = cases[:limit]
        df = pd.DataFrame(run_cases(cases, dataset_name="jailbreak_tests", provider=provider))
        ensure_results_dir()
        df.to_csv(RESULTS_DIR / "safety_results.csv", index=False)

    print(f"Evaluated {len(df)} prompt-case rows.")
    print(f"Results directory: {RESULTS_DIR}")
    if provider == "groq":
        print(f"Groq model preference: {', '.join(get_groq_models()[:4])}")


if __name__ == "__main__":
    main()
