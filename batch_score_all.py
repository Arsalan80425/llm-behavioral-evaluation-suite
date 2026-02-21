"""
Batch score all model results (baseline + improved) across all model directories.
Uses the fixed scorer with correct overall_pass logic and context poisoning rules.
"""

import sys
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

def main():
    total_scored = 0
    errors = []
    
    for model_dir in MODEL_DIRS:
        model_path = RESULTS_DIR / model_dir
        if not model_path.exists():
            print(f"⚠️  Skipping {model_dir} - not found")
            continue
        
        for prompt_type in ["baseline", "improved"]:
            jsonl_files = list(model_path.glob(f"*_{prompt_type}.jsonl"))
            # Skip already-scored files
            jsonl_files = [f for f in jsonl_files if not f.name.startswith("scored_")]
            
            if not jsonl_files:
                print(f"⚠️  No {prompt_type} file for {model_dir}")
                continue
            
            # Use the most recent file
            input_file = sorted(jsonl_files)[-1]
            output_file = input_file.parent / f"scored_{input_file.name}"
            
            # Skip if already scored
            if output_file.exists():
                print(f"⏭️  Already scored: {output_file.name}")
                total_scored += 1
                continue
            
            print(f"\n{'='*60}")
            print(f"Scoring: {model_dir} / {prompt_type}")
            print(f"Input:   {input_file}")
            print(f"Output:  {output_file}")
            print(f"{'='*60}")
            
            try:
                score_existing_results(input_file, output_file)
                total_scored += 1
            except Exception as e:
                print(f"❌ Error scoring {input_file}: {e}")
                errors.append((str(input_file), str(e)))
    
    print(f"\n{'='*60}")
    print(f"BATCH SCORING COMPLETE")
    print(f"{'='*60}")
    print(f"  Scored: {total_scored} files")
    if errors:
        print(f"  Errors: {len(errors)}")
        for path, err in errors:
            print(f"    ❌ {path}: {err[:80]}")
    else:
        print(f"  Errors: None ✅")
    
    print(f"\nTo review all results:")
    print(f"  python human_review.py results/<model_dir>/scored_<file>.jsonl")


if __name__ == "__main__":
    main()
