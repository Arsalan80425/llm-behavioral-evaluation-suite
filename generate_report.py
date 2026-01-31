"""
Report Generator for LLM Behavioral Evaluation Suite
Generates comprehensive markdown reports with model comparisons.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

RESULTS_DIR = Path(__file__).parent / "results"
REPORTS_DIR = Path(__file__).parent / "reports"


def load_results(filepath: Path) -> list[dict]:
    """Load results from a JSONL file."""
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def get_latest_results() -> Optional[Path]:
    """Get the most recent results file."""
    if not RESULTS_DIR.exists():
        return None
    
    files = sorted(RESULTS_DIR.glob("eval_results_*.jsonl"), reverse=True)
    return files[0] if files else None


def analyze_results(results: list[dict]) -> dict:
    """Compute aggregate statistics from results."""
    
    stats = {
        "total_tests": len(results),
        "by_category": defaultdict(lambda: {"count": 0, "errors": 0}),
        "by_model": defaultdict(lambda: {"count": 0, "errors": 0}),
        "by_prompt_type": defaultdict(lambda: {"count": 0, "errors": 0}),
        "by_model_prompt": defaultdict(lambda: {"count": 0, "errors": 0}),
        "models": set(),
        "categories": set(),
        "providers": set()
    }
    
    for r in results:
        category = r.get("category", "Unknown")
        model = r.get("model", "Unknown")
        prompt_type = r.get("prompt_type", "Unknown")
        provider = r.get("provider", "Unknown")
        is_error = r.get("error", False)
        
        stats["models"].add(model)
        stats["categories"].add(category)
        stats["providers"].add(provider)
        
        stats["by_category"][category]["count"] += 1
        stats["by_model"][model]["count"] += 1
        stats["by_prompt_type"][prompt_type]["count"] += 1
        stats["by_model_prompt"][(model, prompt_type)]["count"] += 1
        
        if is_error:
            stats["by_category"][category]["errors"] += 1
            stats["by_model"][model]["errors"] += 1
            stats["by_prompt_type"][prompt_type]["errors"] += 1
            stats["by_model_prompt"][(model, prompt_type)]["errors"] += 1
    
    stats["models"] = sorted(list(stats["models"]))
    stats["categories"] = sorted(list(stats["categories"]))
    stats["providers"] = list(stats["providers"])
    
    return stats


def group_results_by_test(results: list[dict]) -> dict:
    """Group results by test_id for comparison."""
    grouped = defaultdict(list)
    for r in results:
        grouped[r["test_id"]].append(r)
    return grouped


def generate_markdown_report(results: list[dict], output_path: Optional[Path] = None) -> str:
    """Generate a comprehensive markdown report from evaluation results."""
    
    stats = analyze_results(results)
    grouped = group_results_by_test(results)
    
    report = []
    
    # Header
    report.append("# LLM Behavioral Evaluation Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n**Total Test Runs:** {stats['total_tests']}")
    report.append(f"\n**Models Evaluated:** {', '.join(stats['models'])}")
    report.append(f"\n**Providers:** {', '.join(stats['providers'])}")
    
    # Executive Summary
    report.append("\n---\n")
    report.append("## Executive Summary\n")
    total_errors = sum(s["errors"] for s in stats["by_category"].values())
    report.append(f"- **Success Rate:** {((stats['total_tests'] - total_errors) / stats['total_tests'] * 100):.1f}%")
    report.append(f"- **Categories Tested:** {len(stats['categories'])}")
    report.append(f"- **Unique Test Cases:** {len(grouped)}")
    
    # Summary by Category Table
    report.append("\n---\n")
    report.append("## Summary by Category\n")
    report.append("| Category | Tests | Errors | Success Rate |")
    report.append("|----------|-------|--------|--------------|")
    for category in stats["categories"]:
        data = stats["by_category"][category]
        success_rate = ((data["count"] - data["errors"]) / data["count"] * 100) if data["count"] > 0 else 0
        report.append(f"| {category} | {data['count']} | {data['errors']} | {success_rate:.0f}% |")
    
    # Model Comparison Table
    report.append("\n---\n")
    report.append("## Model Comparison\n")
    report.append("| Model | Baseline Tests | Baseline Errors | Improved Tests | Improved Errors |")
    report.append("|-------|----------------|-----------------|----------------|-----------------|")
    for model in stats["models"]:
        baseline = stats["by_model_prompt"].get((model, "baseline"), {"count": 0, "errors": 0})
        improved = stats["by_model_prompt"].get((model, "improved"), {"count": 0, "errors": 0})
        report.append(f"| {model} | {baseline['count']} | {baseline['errors']} | {improved['count']} | {improved['errors']} |")
    
    # Detailed Results by Category
    report.append("\n---\n")
    report.append("## Detailed Results by Category\n")
    
    # Group by category
    by_category = defaultdict(list)
    for test_id, test_results in grouped.items():
        if test_results:
            category = test_results[0]["category"]
            by_category[category].append((test_id, test_results))
    
    for category in sorted(by_category.keys()):
        report.append(f"\n### {category}\n")
        
        for test_id, test_results in by_category[category]:
            # Get test info from first result
            first = test_results[0]
            report.append(f"\n#### Test: `{test_id}`\n")
            report.append(f"**Prompt:** {first['prompt']}\n")
            if first.get("context"):
                report.append(f"\n**Context:**\n```\n{first.get('context', 'N/A')}\n```\n")
            report.append(f"\n**Expected Behavior:** {first['expected_behavior']}\n")
            report.append(f"\n**Failure Mode:** {first['failure_mode']}\n")
            
            # Show all responses grouped by model and prompt type
            report.append("\n**Responses:**\n")
            
            # Sort by model then prompt type
            sorted_results = sorted(test_results, key=lambda x: (x.get("model", ""), x.get("prompt_type", "")))
            
            for r in sorted_results:
                model = r.get("model", "Unknown")
                prompt_type = r.get("prompt_type", "Unknown")
                response = r.get("response", "No response")
                duration = r.get("duration_ms") or 0
                error = r.get("error", False)
                
                # Judge scoring info
                judge_score = r.get("judge_score")
                judge_passes = r.get("judge_passes")
                judge_reasoning = r.get("judge_reasoning", "")
                
                # Determine status emoji
                if error:
                    status = "❌ ERROR"
                elif judge_passes is True:
                    status = "✅ PASS"
                elif judge_passes is False:
                    status = "❌ FAIL"
                else:
                    status = "⚪"  # No score
                
                duration_str = f"{duration:.0f}ms" if duration else "N/A"
                score_str = f"**{judge_score}/5**" if judge_score else "N/A"
                
                report.append(f"\n<details>")
                report.append(f"<summary><b>{model}</b> ({prompt_type}) {status} Score: {score_str} - {duration_str}</summary>\n")
                
                if judge_reasoning:
                    report.append(f"\n> **Judge Reasoning:** {judge_reasoning}\n")
                
                report.append(f"\n```\n{response}\n```\n")
                report.append(f"</details>\n")
    
    # Baseline vs Improved Analysis
    report.append("\n---\n")
    report.append("## Baseline vs Improved Prompt Analysis\n")
    report.append("| Metric | Baseline | Improved |")
    report.append("|--------|----------|----------|")
    baseline_stats = stats["by_prompt_type"].get("baseline", {"count": 0, "errors": 0})
    improved_stats = stats["by_prompt_type"].get("improved", {"count": 0, "errors": 0})
    report.append(f"| Total Tests | {baseline_stats['count']} | {improved_stats['count']} |")
    report.append(f"| Errors | {baseline_stats['errors']} | {improved_stats['errors']} |")
    if baseline_stats['count'] > 0 and improved_stats['count'] > 0:
        baseline_rate = (baseline_stats['count'] - baseline_stats['errors']) / baseline_stats['count'] * 100
        improved_rate = (improved_stats['count'] - improved_stats['errors']) / improved_stats['count'] * 100
        report.append(f"| Success Rate | {baseline_rate:.1f}% | {improved_rate:.1f}% |")
    
    # Key Findings Section
    report.append("\n---\n")
    report.append("## Key Findings\n")
    report.append("> [!NOTE]")
    report.append("> Fill in your analysis after reviewing the detailed responses above.\n")
    report.append("\n### Observations\n")
    report.append("- [ ] Which model performed best overall?")
    report.append("- [ ] Did improved prompts outperform baseline?")
    report.append("- [ ] Any categories where all models struggled?")
    report.append("- [ ] Unexpected behaviors or interesting responses?")
    report.append("\n### Notable Responses\n")
    report.append("_Add specific examples that stood out:_\n")
    report.append("1. ")
    report.append("2. ")
    report.append("3. ")
    
    # Methodology
    report.append("\n---\n")
    report.append("## Methodology\n")
    report.append("- **Evaluation Framework:** LLM Behavioral Evaluation Suite")
    report.append(f"- **Test Cases:** {len(grouped)} unique prompts across {len(stats['categories'])} categories")
    report.append(f"- **Models:** {', '.join(stats['models'])}")
    report.append("- **Prompt Strategy:** A/B testing with baseline vs improved system prompts")
    report.append("- **Metrics:** Error rate, response quality (manual review)")
    
    report_text = "\n".join(report)
    
    # Save report
    if output_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REPORTS_DIR / f"report_{timestamp}.md"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    console.print(f"[green]✓ Comprehensive report generated: {output_path}[/green]")
    
    return report_text


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate evaluation report")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Input results file (default: latest)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output report path"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Combine all results files into one report"
    )
    
    args = parser.parse_args()
    
    if args.all:
        # Combine all results
        all_results = []
        for f in sorted(RESULTS_DIR.glob("eval_results_*.jsonl")):
            console.print(f"Loading: {f.name}")
            all_results.extend(load_results(f))
        if not all_results:
            console.print("[red]No results found.[/red]")
            exit(1)
        console.print(f"Total results: {len(all_results)}")
        generate_markdown_report(all_results, args.output)
    else:
        if args.input:
            results_path = args.input
        else:
            results_path = get_latest_results()
        
        if results_path is None:
            console.print("[red]No results found. Run the evaluation first.[/red]")
            exit(1)
        
        console.print(f"Loading results from: {results_path}")
        results = load_results(results_path)
        generate_markdown_report(results, args.output)
