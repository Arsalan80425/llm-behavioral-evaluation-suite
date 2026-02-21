"""
Human Review Tool for LLM Behavioral Evaluation Suite
Interactive CLI for manually reviewing, confirming, or overriding automated scores.

Usage:
    python human_review.py results/scored_eval_results_20260130_132356.jsonl
    python human_review.py results/scored_eval_results_20260130_132356.jsonl --filter "Jailbreak Resistance"
    python human_review.py results/scored_eval_results_20260130_132356.jsonl --resume
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.markdown import Markdown
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


def print_plain(msg: str):
    """Fallback print when rich is not available."""
    print(msg)


def display_result(result: dict, index: int, total: int):
    """Display a single scored result for human review."""
    test_id = result.get("test_id", "unknown")
    category = result.get("category", "Unknown")
    prompt = result.get("prompt", "")
    expected = result.get("expected_behavior", "")
    failure_mode = result.get("failure_mode", "")
    response = result.get("response", "")
    judge_score = result.get("judge_score")
    judge_reasoning = result.get("judge_reasoning", "")
    judge_passes = result.get("judge_passes")
    rule_scores = result.get("rule_based_scores", {})
    rule_pass_rate = result.get("rule_pass_rate")
    overall_pass = result.get("overall_pass")
    model = result.get("model", "Unknown")
    prompt_type = result.get("prompt_type", "Unknown")

    if HAS_RICH:
        console.print(f"\n{'='*80}")
        console.print(f"[bold cyan]Test {index + 1}/{total}[/bold cyan]  |  "
                      f"[bold]{test_id}[/bold]  |  "
                      f"[dim]{category}[/dim]  |  "
                      f"[yellow]{model}[/yellow] ({prompt_type})")
        console.print(f"{'='*80}")

        # Prompt
        console.print(Panel(prompt, title="[bold]Prompt[/bold]", border_style="blue"))

        # Expected behavior & failure mode
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold green", width=20)
        table.add_column()
        table.add_row("Expected:", expected)
        table.add_row("Failure Mode:", failure_mode)
        console.print(table)

        # Full response
        console.print(Panel(response, title="[bold]Model Response[/bold]", border_style="yellow"))

        # Automated scores
        score_table = Table(title="Automated Scores", show_header=True)
        score_table.add_column("Metric", style="bold")
        score_table.add_column("Value", justify="center")

        judge_emoji = "✅" if judge_passes else ("❌" if judge_passes is False else "⚪")
        score_table.add_row("Judge Score", f"{judge_score}/5" if judge_score else "N/A")
        score_table.add_row("Judge Pass", f"{judge_emoji} {judge_passes}")
        score_table.add_row("Judge Reasoning", judge_reasoning[:100] if judge_reasoning else "N/A")

        if rule_scores:
            for rule_name, rule_val in rule_scores.items():
                rule_emoji = "✅" if rule_val else "❌"
                score_table.add_row(f"Rule: {rule_name}", f"{rule_emoji} {rule_val}")
            score_table.add_row("Rule Pass Rate", f"{rule_pass_rate:.1%}" if rule_pass_rate is not None else "N/A")
        else:
            score_table.add_row("Rules", "[dim]No applicable rules[/dim]")

        overall_emoji = "✅" if overall_pass else "❌"
        score_table.add_row("Overall Pass", f"{overall_emoji} {overall_pass}")

        console.print(score_table)

        # Previous human review if exists
        if result.get("human_reviewed"):
            console.print(Panel(
                f"Score: {result.get('human_score')}/5 | "
                f"Pass: {result.get('human_passes')} | "
                f"Notes: {result.get('human_notes', '')}",
                title="[bold magenta]Previous Human Review[/bold magenta]",
                border_style="magenta"
            ))
    else:
        # Plain text fallback
        print(f"\n{'='*80}")
        print(f"Test {index + 1}/{total}  |  {test_id}  |  {category}  |  {model} ({prompt_type})")
        print(f"{'='*80}")
        print(f"\nPrompt: {prompt}")
        print(f"Expected: {expected}")
        print(f"Failure Mode: {failure_mode}")
        print(f"\nResponse: {response}")
        print(f"\nJudge Score: {judge_score}/5 | Pass: {judge_passes}")
        print(f"Judge Reasoning: {judge_reasoning}")
        if rule_scores:
            print(f"Rules: {rule_scores} | Rate: {rule_pass_rate}")
        print(f"Overall Pass: {overall_pass}")


def get_human_review(result: dict) -> dict:
    """Prompt the human reviewer for their assessment."""
    if HAS_RICH:
        console.print("\n[bold magenta]─── Your Review ───[/bold magenta]")

        # Action choice
        action = Prompt.ask(
            "[bold]Action[/bold] [cyan]c[/cyan]=confirm [yellow]o[/yellow]=override [dim]s[/dim]=skip [green]v[/green]=view full response [red]q[/red]=quit",
            choices=["c", "o", "s", "q", "v"],
            default="c"
        )

        if action == "q":
            return {"action": "quit"}
        elif action == "s":
            return {"action": "skip"}
        elif action == "v":
            # Show full response again
            console.print(Panel(
                result.get("response", ""),
                title="[bold]Full Model Response[/bold]",
                border_style="yellow"
            ))
            return {"action": "view"}
        elif action == "c":
            # Confirm - agree with judge
            notes = Prompt.ask("[dim]Notes (optional, press Enter to skip)[/dim]", default="")
            return {
                "action": "confirm",
                "human_score": result.get("judge_score"),
                "human_passes": result.get("judge_passes"),
                "human_notes": notes if notes else f"Confirmed judge score of {result.get('judge_score')}/5",
                "human_reviewed": True
            }
        elif action == "o":
            # Override
            score = IntPrompt.ask("[bold]Your score (1-5)[/bold]", default=3)
            score = max(1, min(5, score))
            passes = Confirm.ask("[bold]Does this response pass?[/bold]")
            notes = Prompt.ask("[bold]Reasoning / notes[/bold]", default="")
            return {
                "action": "override",
                "human_score": score,
                "human_passes": passes,
                "human_notes": notes if notes else f"Override: {score}/5, {'pass' if passes else 'fail'}",
                "human_reviewed": True
            }
    else:
        # Plain text fallback
        print("\nActions: [c]onfirm  [o]verride  [s]kip  [v]iew full  [q]uit")
        action = input("Action [c]: ").strip().lower() or "c"

        if action == "q":
            return {"action": "quit"}
        elif action == "s":
            return {"action": "skip"}
        elif action == "v":
            print(f"\n{'─'*80}")
            print(result.get("response", ""))
            print(f"{'─'*80}")
            return {"action": "view"}
        elif action == "c":
            notes = input("Notes (optional): ").strip()
            return {
                "action": "confirm",
                "human_score": result.get("judge_score"),
                "human_passes": result.get("judge_passes"),
                "human_notes": notes if notes else f"Confirmed judge score of {result.get('judge_score')}/5",
                "human_reviewed": True
            }
        elif action == "o":
            score = int(input("Your score (1-5): ") or "3")
            passes = input("Pass? (y/n): ").lower().startswith("y")
            notes = input("Reasoning: ").strip()
            return {
                "action": "override",
                "human_score": score,
                "human_passes": passes,
                "human_notes": notes if notes else f"Override: {score}/5",
                "human_reviewed": True
            }

    return {"action": "skip"}


def run_human_review(
    results_path: Path,
    output_path: Optional[Path] = None,
    category_filter: Optional[str] = None,
    resume: bool = False
):
    """Main human review loop."""

    # Load results
    results = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    if not results:
        print("No results found in file.")
        return

    # Filter by category if specified
    if category_filter:
        results = [r for r in results if category_filter.lower() in r.get("category", "").lower()]
        if not results:
            print(f"No results matching category filter: {category_filter}")
            return

    # Find starting index for resume
    start_idx = 0
    if resume:
        for i, r in enumerate(results):
            if not r.get("human_reviewed"):
                start_idx = i
                break
        else:
            print("All results have been reviewed!")
            return

    total = len(results)
    reviewed_count = sum(1 for r in results if r.get("human_reviewed"))
    overridden_count = 0

    if HAS_RICH:
        console.print(Panel(
            f"File: {results_path}\n"
            f"Total results: {total}\n"
            f"Already reviewed: {reviewed_count}\n"
            f"Starting from: {start_idx + 1}\n"
            f"Category filter: {category_filter or 'All'}\n\n"
            f"[bold]Actions:[/bold]\n"
            f"  [cyan][c]onfirm[/cyan]  — Agree with automated judge score\n"
            f"  [yellow][o]verride[/yellow] — Provide your own score (1-5)\n"
            f"  [dim][s]kip[/dim]     — Skip this result\n"
            f"  [red][q]uit[/red]     — Save and exit",
            title="[bold green]🔍 Human Review Session[/bold green]",
            border_style="green"
        ))
    else:
        print(f"\nHuman Review Session")
        print(f"File: {results_path}")
        print(f"Total: {total} | Reviewed: {reviewed_count} | Starting from: {start_idx + 1}")
        print(f"Actions: [c]onfirm  [o]verride  [s]kip  [q]uit\n")

    # Review loop
    for i in range(start_idx, total):
        result = results[i]

        # Skip already reviewed if resuming
        if resume and result.get("human_reviewed"):
            continue

        display_result(result, i, total)
        
        # Review loop with view support
        while True:
            review = get_human_review(result)
            if review["action"] != "view":
                break

        if review["action"] == "quit":
            if HAS_RICH:
                console.print("\n[yellow]Saving progress and exiting...[/yellow]")
            break
        elif review["action"] == "skip":
            continue
        elif review["action"] in ("confirm", "override"):
            results[i]["human_score"] = review["human_score"]
            results[i]["human_passes"] = review["human_passes"]
            results[i]["human_notes"] = review["human_notes"]
            results[i]["human_reviewed"] = True
            reviewed_count += 1
            if review["action"] == "override":
                overridden_count += 1

    # Save results
    if output_path is None:
        output_path = results_path  # Overwrite in-place

    with open(output_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    # Summary
    total_reviewed = sum(1 for r in results if r.get("human_reviewed"))

    if HAS_RICH:
        summary = Table(title="Review Session Summary")
        summary.add_column("Metric", style="bold")
        summary.add_column("Value", justify="center")
        summary.add_row("Total Results", str(total))
        summary.add_row("Reviewed This Session", str(reviewed_count - (sum(1 for r in results if r.get("human_reviewed")) - reviewed_count)))
        summary.add_row("Total Reviewed", str(total_reviewed))
        summary.add_row("Overrides", str(overridden_count))
        summary.add_row("Remaining", str(total - total_reviewed))
        summary.add_row("Saved To", str(output_path))
        console.print(summary)

        if total_reviewed == total:
            console.print("\n[bold green]✅ All results have been reviewed![/bold green]")

            # Compute final stats
            human_pass_rate = sum(1 for r in results if r.get("human_passes")) / total * 100
            avg_score = sum(r.get("human_score", 0) or 0 for r in results) / total
            console.print(f"   Human Pass Rate: {human_pass_rate:.1f}%")
            console.print(f"   Avg Human Score: {avg_score:.1f}/5")
    else:
        print(f"\nSaved to: {output_path}")
        print(f"Reviewed: {total_reviewed}/{total}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Human Review Tool for LLM Behavioral Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python human_review.py results/scored_eval_results_20260130_132356.jsonl
  python human_review.py results/scored_eval_results_20260130_132356.jsonl --filter "Jailbreak"
  python human_review.py results/scored_eval_results_20260130_132356.jsonl --resume
  python human_review.py results/scored_eval_results_20260130_132356.jsonl -o results/reviewed.jsonl
        """
    )
    parser.add_argument("results_file", type=Path, help="Path to scored JSONL results file")
    parser.add_argument("--output", "-o", type=Path, help="Output path (default: overwrite input)")
    parser.add_argument("--filter", "-f", type=str, help="Filter by category name (partial match)")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume from last unreviewed result")

    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Error: File not found: {args.results_file}")
        sys.exit(1)

    run_human_review(
        results_path=args.results_file,
        output_path=args.output,
        category_filter=args.filter,
        resume=args.resume
    )
