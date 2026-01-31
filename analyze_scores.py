import json
from pathlib import Path

results_path = Path("results/scored_eval_results_20260130_132356.jsonl")

results = []
with open(results_path) as f:
    for line in f:
        if line.strip():
            results.append(json.loads(line))

print(f"Total results: {len(results)}")
print(f"\nJudge Pass Rate: {sum(r.get('judge_passes', False) for r in results)}/{len(results)}")
print(f"Overall Pass Rate: {sum(r.get('overall_pass', False) for r in results)}/{len(results)}")

print("\nFailed tests (overall_pass=False):")
failed = [r for r in results if not r.get('overall_pass')]
for r in failed[:10]:
    print(f"  {r['test_id'][:30]:<30} | Judge: {r.get('judge_score')}/5 | Rule: {r.get('rule_pass_rate', 0):.2f}")

print("\n5/5 Perfect scores:")
perfect = [r for r in results if r.get('judge_score') == 5]
for r in perfect[:5]:
    print(f"  {r['test_id']}")
