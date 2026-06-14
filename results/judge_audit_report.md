# Judge Audit Report — Enterprise RAG Evaluation Lab

**Generated:** 2026-06-14T21:54:03.913934
**Judge model:** claude-sonnet-4-5 (Claude Sonnet 4.6)
**Audit mode:** manual (USE_CLAUDE_JUDGE not set)
**Sample size:** 277 records

## Status

API-based audit was not run. A manual audit prompt has been generated at:
`C:\Users\arsal\Desktop\LLM Behavioral Evaluation Suite\results\judge_audit_prompt.md`

Paste that file into Claude Sonnet 4.6 to get structured findings.
Then run this script again with `USE_CLAUDE_JUDGE=true ANTHROPIC_API_KEY=<key>` to process findings automatically.

## Structural Audit (Pre-Claude)

The following structural checks passed before Claude review:
- No duplicate (case_id, prompt_version) pairs
- All scores in valid ranges (1–5 for rubric scores, 0–1 for citation_score)
- No NaN values in score columns
- No rows where hallucination_flag=True AND overall_score >= 4.0 simultaneously
- No wrong pairwise winners (declared winner always has higher overall score)
- No ties with score difference > 0.5