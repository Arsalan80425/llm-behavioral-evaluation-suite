"""
Batch score all model results (baseline + improved) across all model directories.
Uses the fixed scorer with retry logic, API key rotation, and rate limit protection.

Usage:
  python batch_score_all.py          # Score new files only
  python batch_score_all.py --force  # Re-score ALL files (overwrites existing scored files)
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.scorer import score_existing_results

RESULTS_DIR = Path(__file__).parent / "results"

MODEL_DIRS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "moonshotai_kimi-k2-instruct-0905",
    "qwen_qwen3-32b",
    "openai_gpt-oss-120b",
    "mistral",
    "phi3",
]


def check_judge_failures(scored_file):
    """Check how many judge failures exist in a scored file."""
    total = 0
    failures = 0
    with open(scored_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                total += 1
                if record.get('judge_score') is None:
                    failures += 1
    return total, failures


def main():
    force = "--force" in sys.argv
    
    if force:
        print("🔄 FORCE MODE: Re-scoring all files (overwriting existing)")
    else:
        print("📋 Normal mode: Scoring new files only")
    
    total_scored = 0
    total_skipped = 0
    errors = []
    keys_exhausted = False
    
    for model_dir in MODEL_DIRS:
        if keys_exhausted:
            print(f"\n⚠️  Skipping {model_dir} - API keys exhausted")
            continue
            
        model_path = RESULTS_DIR / model_dir
        if not model_path.exists():
            print(f"⚠️  Skipping {model_dir} - not found")
            continue
        
        for prompt_type in ["baseline", "improved"]:
            if keys_exhausted:
                break
                
            jsonl_files = list(model_path.glob(f"*_{prompt_type}.jsonl"))
            # Skip already-scored files
            jsonl_files = [f for f in jsonl_files if not f.name.startswith("scored_")]
            
            if not jsonl_files:
                print(f"⚠️  No {prompt_type} file for {model_dir}")
                continue
            
            # Use the most recent file
            input_file = sorted(jsonl_files)[-1]
            output_file = input_file.parent / f"scored_{input_file.name}"
            
            # Check if already scored and whether it needs re-scoring
            if output_file.exists() and not force:
                total, failures = check_judge_failures(output_file)
                if failures == 0:
                    print(f"⏭️  Already scored (0 failures): {output_file.name}")
                    total_skipped += 1
                    continue
                else:
                    print(f"🔁 Re-scoring (has {failures}/{total} judge failures): {output_file.name}")
            elif output_file.exists() and force:
                total, failures = check_judge_failures(output_file)
                if failures == 0:
                    print(f"⏭️  Skipping (already has 0 failures): {output_file.name}")
                    total_skipped += 1
                    continue
                print(f"🔄 Force re-scoring: {output_file.name} ({failures}/{total} failures)")
            
            print(f"\n{'='*60}")
            print(f"Scoring: {model_dir} / {prompt_type}")
            print(f"Input:   {input_file}")
            print(f"Output:  {output_file}")
            print(f"{'='*60}")
            
            try:
                scored_results = score_existing_results(input_file, output_file)
                total_scored += 1
                
                # Check for key exhaustion
                for r in scored_results:
                    reasoning = r.get("judge_reasoning", "")
                    if reasoning and "ALL_KEYS_EXHAUSTED" in str(reasoning):
                        keys_exhausted = True
                        print("\n⚠️  API KEYS EXHAUSTED! Stopping batch scoring.")
                        print("   Please check/update your API keys in config.json")
                        break
                        
            except Exception as e:
                print(f"❌ Error scoring {input_file}: {e}")
                errors.append((str(input_file), str(e)))
    
    print(f"\n{'='*60}")
    print(f"BATCH SCORING COMPLETE")
    print(f"{'='*60}")
    print(f"  Scored: {total_scored} files")
    print(f"  Skipped: {total_skipped} files (already OK)")
    if keys_exhausted:
        print(f"  ⚠️  API Keys: EXHAUSTED - some files may not have been scored")
    if errors:
        print(f"  Errors: {len(errors)}")
        for path, err in errors:
            print(f"    ❌ {path}: {err[:80]}")
    else:
        print(f"  Errors: None ✅")
    
    print(f"\nNext steps:")
    print(f"  1. python auto_human_review.py  (re-run auto review)")
    print(f"  2. python generate_dashboard_data.py  (regenerate dashboard)")


if __name__ == "__main__":
    main()
