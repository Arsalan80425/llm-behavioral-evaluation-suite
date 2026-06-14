# LLM Evaluation & Enterprise RAG Reliability Lab

**Unified Behavioral Evaluation Suite + Enterprise RAG Prompt Evaluation Lab**

Static GitHub Pages dashboard plus local Python evaluation pipeline for LLM behavior testing, prompt A/B comparison, RAG groundedness evaluation, hallucination checks, jailbreak resistance, regression stability, and RLHF-style preference data generation.

The public demo is a single GitHub Pages site with two professional view modes:

1. **Behavioral Evaluation Suite** - the preserved original static dashboard for behavioral safety, prompt engineering impact, model comparison, category performance, methodology, and test-case exploration.
2. **Enterprise RAG Prompt Evaluation Lab** - a new static dashboard module for enterprise RAG prompt evaluation, prompt-version comparison, failure-case review, preference data preview, and local Groq verification status.

The GitHub Pages demo is static and safe: it uses exported JSON from `docs/data/`, does not include API keys, does not expose `.env`, and does not call Groq or any LLM API from browser JavaScript.

## Overview

Enterprise RAG Prompt Evaluation Lab is a local-first evaluation harness for enterprise policy assistants. It uses a fictional company knowledge base, deterministic retrieval, mock response generation, heuristic rubric scoring, pairwise prompt comparisons, safety tests, regression checks, static GitHub Pages exports, and an optional local Streamlit dashboard.

The default demo does not require paid APIs. Optional Groq real-model generation is exposed through environment variables and `--real-llm`, but the project runs end-to-end in mock/local mode. Groq Llama 3.3 70B can be verified locally with `python evals/smoke_test_groq.py`; the browser demo only displays saved verification results.

## Why This Project Matters

RAG assistants often fail in subtle ways: they cite the wrong source, invent missing policy details, comply with prompt injection, or regress when a prompt is edited. This project shows a release-style workflow for catching those failures before deployment.

## Features

- Four prompt versions: baseline, optimized, safety-constrained, and RAG-grounded.
- Fictional enterprise policy knowledge base covering HR, travel, privacy, support, security, AI usage, and refunds.
- 55 core evaluation cases plus 20 jailbreak tests, 20 hallucination tests, and 15 regression tests.
- Local TF-IDF retrieval with policy-section citations.
- Rubric-based scoring for accuracy, groundedness, instruction following, safety, refusal quality, citations, hallucination, jailbreak failure, and JSON validity.
- A/B and pairwise prompt comparison.
- RLHF-style preference dataset generation with rationales.
- Regression report for prompt release checks.
- Static GitHub Pages dashboard with two view modes, filters, charts, failure explorer, prompt comparison, preference preview, and Groq verification status.
- Optional Streamlit dashboard for local exploration.

## Architecture

```text
prompts/       Prompt versions under test
datasets/      Fictional policy KB and JSONL evaluation datasets
rubrics/       Human-readable rubric definitions
evals/         Retrieval, LLM provider client, scoring, evaluation, ranking, safety, regression scripts
app/           Streamlit dashboard
results/       Generated CSV, JSONL, and markdown reports
src/           Preserved legacy behavioral-evaluation pipeline
docs/          Preserved static dashboard artifacts from the earlier project
```

## GitHub Pages Demo

The GitHub Pages site lives in `docs/` and is designed to be deployed as one public link.

- `docs/index.html`: unified dashboard shell, view switcher, behavioral view, and Enterprise RAG view.
- `docs/data.js`: preserved behavioral evaluation data.
- `docs/data/rag_eval_results.json`: exported Enterprise RAG result rows.
- `docs/data/rag_preference_dataset.json`: exported RLHF-style pairwise records.
- `docs/data/rag_failure_cases.json`: exported risky or failed cases.
- `docs/data/rag_summary_report.json`: computed aggregate metrics and local Groq verification status.
- `docs/data/rag_prompts.json`: prompt-version descriptions and prompt text.

Refresh the Enterprise RAG static data after running evaluations:

```bash
python evals/export_static_demo.py
```

Then commit `docs/index.html` and the generated `docs/data/*.json` files. Do not commit `.env`, `config.json`, or API keys.

## Dataset Design

The knowledge base is in `datasets/enterprise_policy_knowledge_base.md` and includes fictional policies for:

- Remote work
- Laptop reimbursement
- Travel expenses
- Data privacy
- Customer data handling
- Escalation policy
- Employee leave
- Acceptable AI tool usage
- Security incident reporting
- Refund and support policy

Evaluation data is split by purpose:

- `datasets/eval_questions.jsonl`: normal, ambiguous, missing-context, conflicting-context, structured-output, and safety-sensitive tests.
- `datasets/jailbreak_tests.jsonl`: prompt injection, policy invention, citation bypass, sensitive data exposure, and unsafe internal information requests.
- `datasets/hallucination_tests.jsonl`: questions where the correct answer is that the knowledge base does not contain the requested detail.
- `datasets/regression_tests.jsonl`: fixed release checks with minimum expected scores.

## Prompt Versions

- `baseline_prompt.md`: minimal helpful assistant prompt.
- `optimized_prompt.md`: adds accuracy, completeness, uncertainty handling, and tone constraints.
- `safety_constrained_prompt.md`: adds privacy, jailbreak resistance, refusal rules, and escalation behavior.
- `rag_grounded_prompt.md`: requires retrieved-context-only answers, citations, insufficient-context handling, evidence separation, and ambiguity handling.

## Evaluation Rubrics

Rubrics live in `rubrics/`:

- Accuracy
- Groundedness
- Safety
- Instruction following
- Refusal quality

The scoring implementation is in `evals/scoring.py`. It is intentionally heuristic by default so the demo is reproducible without paid judge models. Optional real generation is isolated in `evals/llm_client.py`.

## Metrics Tracked

- Overall average score
- Accuracy score
- Groundedness score
- Instruction-following score
- Safety score
- Refusal-quality score
- Citation pass rate
- Hallucination rate
- Jailbreak failure rate
- JSON validity for structured-output cases
- Regression pass rate
- Pairwise preference win rate

## RLHF-Style Preference Data

Run:

```bash
python evals/pairwise_ranking.py
```

This compares:

- Baseline vs optimized
- Optimized vs safety-constrained
- Safety-constrained vs RAG-grounded

It writes `results/preference_dataset.jsonl` with response A, response B, winner, rationale, and overall scores.

## Safety and Jailbreak Testing

Run:

```bash
python evals/safety_tests.py
```

The safety suite checks whether prompts resist attempts to reveal hidden instructions, invent policy, bypass citations, expose customer data, leak internal incident details, or follow malicious embedded instructions.

## Regression Testing

Run:

```bash
python evals/regression_check.py
```

Regression checks flag groundedness drops, new hallucinations, safety score drops, missing citations, and failed missing-context refusals. Results are written to `results/regression_report.md` and appended to `results/summary_report.md`.

### Optional Groq Smoke Test

This project uses Llama 70B via Groq (`llama-3.3-70b-versatile`). Model availability on Groq can change, so please verify that this model is available in your Groq console.

```bash
python evals/smoke_test_groq.py
```

This verifies real Groq connectivity without running the full evaluation suite or consuming much free-tier quota.

## How To Run Locally

1. Create a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the evaluation:

```bash
python evals/run_eval.py
```

Equivalent explicit mock mode:

```bash
python evals/run_eval.py --provider mock --limit 10
```

To run a small Groq-backed smoke test with free-tier keys:

```bash
python evals/run_eval.py --provider groq --limit 10
```

The Groq setup reads keys from `.env` (`GROQ_API_KEY`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, or `GROQ_API_KEYS`) or from the ignored legacy `config.json`. The primary Groq model is `llama-3.3-70b-versatile`, with `llama-3.1-8b-instant` as an optional fallback. GitHub Pages never calls Groq from browser JavaScript — all Groq calls happen only from local Python scripts.

Real Groq mode sends retrieved policy context and user questions to Groq. Keep mock mode for private or sensitive datasets. If Groq is unavailable, the runner records a clean fallback label such as `mock_after_error` and continues with deterministic mock responses.

4. Generate preference data:

```bash
python evals/pairwise_ranking.py
```

5. Run regression checks:

```bash
python evals/regression_check.py
```

6. Run safety tests:

```bash
python evals/safety_tests.py
```

7. Export static GitHub Pages data:

```bash
python evals/export_static_demo.py
```

8. Optional local Streamlit dashboard:

```bash
streamlit run app/dashboard.py
```

9. Optional Groq smoke test with your own local API key:

```bash
python evals/smoke_test_groq.py
```

Small Groq-backed evaluation:

```bash
python evals/run_eval.py --provider groq --limit 1
```

The GitHub Pages page never sends these requests. Groq calls only happen from the local Python scripts.

## Example Results

After running the scripts, inspect:

- `results/eval_results.csv`
- `results/preference_dataset.jsonl`
- `results/failure_cases.md`
- `results/summary_report.md`
- `results/regression_report.md`
- `results/safety_results.csv`

Expected trend in local mock mode: the baseline prompt performs worst on citations, hallucination refusal, and jailbreak resistance; the RAG-grounded prompt performs strongest on groundedness and citation discipline.

## Recruiter Summary

- Built a prompt evaluation workflow for enterprise RAG assistants.
- Compared baseline, optimized, safety-constrained, and RAG-grounded prompts.
- Created rubric-based evaluation for accuracy, groundedness, instruction following, safety, and refusal quality.
- Generated RLHF-style preference data with rationales.
- Tested hallucination, missing-context behavior, jailbreak resistance, and prompt-injection robustness.
- Visualized evaluation metrics in an interactive dashboard.

## Resume Bullets

- Built an Enterprise RAG Prompt Evaluation Lab to compare baseline, optimized, safety-constrained, and RAG-grounded prompts across 100+ test cases using rubric-based scoring, pairwise preference ranking, hallucination checks, jailbreak tests, and regression analysis.
- Generated RLHF-style preference datasets with scoring rationales to support prompt optimization and model behavior analysis.
- Improved groundedness and safety evaluation by enforcing citation checks, missing-context refusal behavior, and jailbreak resistance testing.

## How This Maps To AI Prompt Engineer / LLM Evaluation Roles

This project demonstrates prompt versioning, rubric design, dataset construction, RAG retrieval evaluation, citation enforcement, hallucination testing, jailbreak testing, preference data generation, regression detection, and dashboard communication. Those are core workflows for prompt engineering, LLM evaluation, RAG reliability, model QA, and AI product release readiness.

## Tech Stack

- Python
- Streamlit
- pandas
- numpy
- scikit-learn
- PyYAML
- Plotly
- python-dotenv

## Future Improvements

- Add optional OpenAI or Anthropic generation in `USE_REAL_LLM=true` mode.
- Replace TF-IDF retrieval with sentence-transformer embeddings.
- Add optional LLM-as-judge scoring in `USE_LLM_JUDGE=true` mode.
- Add a CI workflow for prompt regression tests.
- Add pytest coverage for scorer edge cases.
- Add screenshot assets from the Streamlit dashboard.

## Legacy Assets

The original behavioral evaluation suite files under `src/`, `data/`, `reports/`, `docs/`, and historical `results/` are preserved for reference. The new portfolio-grade RAG/RLHF workflow lives in `prompts/`, `datasets/`, `rubrics/`, `evals/`, `app/`, and the latest generated result files.
