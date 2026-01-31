import json
from pathlib import Path
from collections import defaultdict

results_path = Path("results/scored_eval_results_20260130_193746.jsonl")

results = []
with open(results_path) as f:
    for line in f:
        if line.strip():
            results.append(json.loads(line))

# Separate by prompt type
baseline = [r for r in results if r['prompt_type'] == 'baseline']
improved = [r for r in results if r['prompt_type'] == 'improved']

print("=" * 60)
print("A/B PROMPT COMPARISON ANALYSIS")
print("=" * 60)
print(f"\nTotal runs: {len(results)} (25 baseline + 25 improved)")

# Overall metrics
print("\n" + "=" * 60)
print("OVERALL JUDGE SCORES")
print("=" * 60)
baseline_passes = sum(r.get('judge_passes', False) for r in baseline)
improved_passes = sum(r.get('judge_passes', False) for r in improved)

baseline_avg = sum(r.get('judge_score', 0) for r in baseline if r.get('judge_score')) / len([r for r in baseline if r.get('judge_score')])
improved_avg = sum(r.get('judge_score', 0) for r in improved if r.get('judge_score')) / len([r for r in improved if r.get('judge_score')])

print(f"\nBaseline:  {baseline_passes}/25 pass ({baseline_passes/25*100:.0f}%) | Avg: {baseline_avg:.2f}/5")
print(f"Improved:  {improved_passes}/25 pass ({improved_passes/25*100:.0f}%) | Avg: {improved_avg:.2f}/5")
print(f"\nImprovement: +{improved_passes - baseline_passes} passes | +{improved_avg - baseline_avg:.2f} score")

# Category breakdown
print("\n" + "=" * 60)
print("CATEGORY BREAKDOWN")
print("=" * 60)

categories = defaultdict(lambda: {'baseline': [], 'improved': []})
for r in results:
    categories[r['category']][r['prompt_type']].append(r.get('judge_score', 0))

print(f"\n{'Category':<35} | {'Baseline':<10} | {'Improved':<10} | Δ")
print("-" * 75)

for cat in sorted(categories.keys()):
    baseline_scores = categories[cat]['baseline']
    improved_scores = categories[cat]['improved']
    
    b_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0
    i_avg = sum(improved_scores) / len(improved_scores) if improved_scores else 0
    delta = i_avg - b_avg
    
    delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}"
    print(f"{cat:<35} | {b_avg:.1f}/5      | {i_avg:.1f}/5      | {delta_str}")

# Biggest improvements
print("\n" + "=" * 60)
print("BIGGEST IMPROVEMENTS (Baseline → Improved)")
print("=" * 60)

test_improvements = []
for test_id in set(r['test_id'] for r in results):
    baseline_r = next((r for r in baseline if r['test_id'] == test_id), None)
    improved_r = next((r for r in improved if r['test_id'] == test_id), None)
    
    if baseline_r and improved_r:
        b_score = baseline_r.get('judge_score', 0) or 0
        i_score = improved_r.get('judge_score', 0) or 0
        improvement = i_score - b_score
        
        if improvement > 0:
            test_improvements.append({
                'test_id': test_id,
                'category': baseline_r['category'],
                'baseline_score': b_score,
                'improved_score': i_score,
                'improvement': improvement
            })

test_improvements.sort(key=lambda x: x['improvement'], reverse=True)

for t in test_improvements[:10]:
    print(f"\n{t['test_id']}")
    print(f"  Category: {t['category']}")
    print(f"  {t['baseline_score']}/5 → {t['improved_score']}/5 (+{t['improvement']})")

# Failures
print("\n" + "=" * 60)
print("TESTS WHERE IMPROVED STILL FAILED (Score ≤ 2)")
print("=" * 60)

improved_failures = [r for r in improved if r.get('judge_score', 0) <= 2]
for r in improved_failures:
    print(f"\n{r['test_id']} ({r['category']})")
    print(f"  Judge Score: {r.get('judge_score')}/5")
    print(f"  Reasoning: {r.get('judge_reasoning', 'N/A')[:100]}")

print("\n" + "=" * 60)
