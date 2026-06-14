"""Streamlit dashboard for the Enterprise RAG Prompt Evaluation Lab."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "results"
PROMPTS_DIR = ROOT_DIR / "prompts"


st.set_page_config(
    page_title="Enterprise RAG Prompt Evaluation Lab",
    page_icon="",
    layout="wide",
)


@st.cache_data
def load_results() -> pd.DataFrame:
    path = RESULTS_DIR / "eval_results.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "model_used" not in df.columns:
        df["model_used"] = df["model"] if "model" in df.columns else "mock"
    if "error" not in df.columns:
        df["error"] = None
    return df


@st.cache_data
def load_jsonl_preview(path: Path, limit: int = 20) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= limit:
                break
    return records


@st.cache_data
def load_prompts() -> dict[str, str]:
    return {
        path.stem.replace("_prompt", ""): path.read_text(encoding="utf-8")
        for path in sorted(PROMPTS_DIR.glob("*_prompt.md"))
    }


def metric_cards(df: pd.DataFrame) -> None:
    """Render top-line evaluation metrics."""
    regression_path = RESULTS_DIR / "regression_summary.csv"
    regression_pass_rate = None
    if regression_path.exists():
        regression_df = pd.read_csv(regression_path)
        if not regression_df.empty:
            regression_pass_rate = regression_df["passed"].mean()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Avg Overall", f"{df['overall_score'].mean():.2f}")
    c2.metric("Groundedness", f"{df['groundedness_score'].mean():.2f}")
    c3.metric("Hallucination Rate", f"{df['hallucination_flag'].mean():.1%}")
    c4.metric("Jailbreak Failure", f"{df['jailbreak_failure_flag'].mean():.1%}")
    c5.metric("Citation Pass", f"{df['citation_score'].mean():.1%}")
    c6.metric("Regression Pass", "Run checks" if regression_pass_rate is None else f"{regression_pass_rate:.1%}")


def charts(df: pd.DataFrame) -> None:
    """Render dashboard charts."""
    left, right = st.columns(2)
    score_df = df.groupby("prompt_version", as_index=False)["overall_score"].mean()
    left.plotly_chart(px.bar(score_df, x="prompt_version", y="overall_score", title="Average Score by Prompt Version", range_y=[0, 5]), use_container_width=True)

    hallucination_df = df.groupby("prompt_version", as_index=False)["hallucination_flag"].mean()
    right.plotly_chart(px.bar(hallucination_df, x="prompt_version", y="hallucination_flag", title="Hallucination Rate by Prompt Version", labels={"hallucination_flag": "rate"}, range_y=[0, 1]), use_container_width=True)

    left2, right2 = st.columns(2)
    safety_df = df.groupby("prompt_version", as_index=False)["safety_score"].mean()
    left2.plotly_chart(px.bar(safety_df, x="prompt_version", y="safety_score", title="Safety Score by Prompt Version", range_y=[0, 5]), use_container_width=True)

    category_df = df.groupby(["prompt_version", "category"], as_index=False)["overall_score"].mean()
    right2.plotly_chart(px.bar(category_df, x="category", y="overall_score", color="prompt_version", barmode="group", title="Category-Level Performance", range_y=[0, 5]), use_container_width=True)

    pairwise_path = RESULTS_DIR / "preference_dataset.jsonl"
    pairwise_records = load_jsonl_preview(pairwise_path, limit=10000)
    if pairwise_records:
        pairwise_df = pd.DataFrame(pairwise_records)
        win_df = pairwise_df.groupby(["comparison", "winner"], as_index=False).size()
        st.plotly_chart(px.bar(win_df, x="comparison", y="size", color="winner", barmode="group", title="Pairwise Preference Win Rate"), use_container_width=True)


def prompt_comparison() -> None:
    """Render prompt version comparison."""
    prompts = load_prompts()
    st.subheader("Prompt Comparison")
    selected = st.multiselect("Prompt versions", list(prompts.keys()), default=list(prompts.keys()))
    cols = st.columns(max(len(selected), 1))
    for col, name in zip(cols, selected):
        col.markdown(f"**{name}**")
        col.code(prompts[name], language="markdown")


def failure_explorer(df: pd.DataFrame) -> None:
    """Render failed and risky cases."""
    st.subheader("Failure Case Explorer")
    failures = df[
        (df["overall_score"] < 4.0)
        | (df["hallucination_flag"] == True)
        | (df["jailbreak_failure_flag"] == True)
        | (df["citation_score"] == 0)
    ].copy()
    if failures.empty:
        st.info("No failure cases were detected in the current result file.")
        return
    selected_case = st.selectbox("Failure case", failures["case_id"].drop_duplicates().tolist())
    st.dataframe(failures[failures["case_id"] == selected_case], use_container_width=True)


def preference_preview() -> None:
    """Render RLHF-style preference data preview."""
    st.subheader("RLHF-Style Preference Dataset Preview")
    records = load_jsonl_preview(RESULTS_DIR / "preference_dataset.jsonl", limit=25)
    if not records:
        st.info("Run `python evals/pairwise_ranking.py` to generate `results/preference_dataset.jsonl`.")
        return
    st.dataframe(pd.DataFrame(records), use_container_width=True)


def workflow_mapping() -> None:
    st.subheader("Production Workflow Mapping")
    st.markdown(
        """
This lab mirrors a production LLM evaluation workflow: prompts are versioned, RAG context is retrieved locally, each response is scored with explicit rubrics, safety and missing-context behavior are checked, regressions are tracked before release, and pairwise preference data is generated for RLHF-style review or future model tuning.
"""
    )


def main() -> None:
    st.title("LLM Prompt Evaluation & RLHF Preference Lab")
    st.caption("Rubric-based LLM testing, prompt A/B comparison, RAG groundedness evaluation, safety testing, and RLHF-style preference data generation.")

    df = load_results()
    if df.empty:
        st.info("No evaluation results found. Run `python evals/run_eval.py` from the project root, then refresh this dashboard.")
        return

    with st.sidebar:
        st.header("Filters")
        prompt_versions = sorted(df["prompt_version"].dropna().unique())
        datasets = sorted(df["dataset"].dropna().unique())
        categories = sorted(df["category"].dropna().unique())
        models = sorted(df["model_used"].dropna().unique()) if "model_used" in df.columns else []
        selected_prompts = st.multiselect("Prompt version", prompt_versions, default=prompt_versions)
        selected_datasets = st.multiselect("Dataset", datasets, default=datasets)
        selected_categories = st.multiselect("Category", categories, default=categories)
        selected_models = st.multiselect("Model/source", models, default=models) if models else []

    filtered = df[
        df["prompt_version"].isin(selected_prompts)
        & df["dataset"].isin(selected_datasets)
        & df["category"].isin(selected_categories)
    ]
    if selected_models:
        filtered = filtered[filtered["model_used"].isin(selected_models)]

    if filtered.empty:
        st.warning("No rows match the selected filters.")
        return

    metric_cards(filtered)
    charts(filtered)

    tabs = st.tabs(["Results", "Failures", "Prompts", "Preferences", "Workflow"])
    with tabs[0]:
        st.subheader("Evaluation Results")
        st.dataframe(filtered, use_container_width=True, hide_index=True)
    with tabs[1]:
        failure_explorer(filtered)
    with tabs[2]:
        prompt_comparison()
    with tabs[3]:
        preference_preview()
    with tabs[4]:
        workflow_mapping()


if __name__ == "__main__":
    main()
