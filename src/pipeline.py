"""
LLM Behavioral Evaluation Pipeline
Supports both Ollama (local) and Groq API with automatic key rotation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# =============================================================================
# PROVIDER IMPORTS (with graceful fallbacks)
# =============================================================================

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from prompts import get_system_prompt_for_category

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
RESULTS_DIR = Path(__file__).parent.parent / "results"
DATA_DIR = Path(__file__).parent.parent / "data"


def load_config() -> dict:
    """Load configuration from config.json"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "groq": {"api_keys": [], "models": ["llama-3.3-70b-versatile"]},
        "ollama": {"models": ["llama3"]},
        "default_provider": "ollama"
    }


CONFIG = load_config()


# =============================================================================
# GROQ CLIENT WITH KEY ROTATION
# =============================================================================

class GroqClientWithFallback:
    """Groq client that rotates through API keys on failure."""
    
    def __init__(self, api_keys: list[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.api_keys and GROQ_AVAILABLE:
            self.client = Groq(api_key=self.api_keys[self.current_key_index])
    
    def _rotate_key(self):
        """Switch to next API key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        console.print(f"[yellow]⟳ Rotating to API key {self.current_key_index + 1}/{len(self.api_keys)}[/yellow]")
        self._init_client()
    
    def chat(self, model: str, messages: list[dict], max_retries: int = 3) -> dict:
        """Send chat request with automatic key rotation on failure."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024
                )
                return {
                    "content": response.choices[0].message.content,
                    "model": model,
                    "provider": "groq",
                    "key_index": self.current_key_index
                }
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Rotate key on rate limit or auth errors
                if "rate" in error_str or "limit" in error_str or "401" in error_str or "429" in error_str:
                    self._rotate_key()
                else:
                    raise e
        
        raise last_error


# Initialize Groq client
groq_client = None
if GROQ_AVAILABLE and CONFIG.get("groq", {}).get("api_keys"):
    groq_client = GroqClientWithFallback(CONFIG["groq"]["api_keys"])


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def load_dataset(path: Optional[Path] = None) -> dict:
    """Load the evaluation dataset from JSON."""
    if path is None:
        path = DATA_DIR / "evaluation_dataset.json"
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def query_ollama(model: str, system_prompt: str, user_content: str) -> dict:
    """Query Ollama (local LLM)."""
    if not OLLAMA_AVAILABLE:
        return {"response": "[ERROR] Ollama not installed", "error": True}
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        start_time = datetime.now()
        response = ollama.chat(model=model, messages=messages)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "response": response["message"]["content"],
            "model": model,
            "provider": "ollama",
            "duration_ms": duration,
            "error": False
        }
    except Exception as e:
        return {"response": f"[ERROR] {str(e)}", "model": model, "provider": "ollama", "error": True}


def query_groq(model: str, system_prompt: str, user_content: str) -> dict:
    """Query Groq API."""
    if not GROQ_AVAILABLE or groq_client is None:
        return {"response": "[ERROR] Groq not available", "error": True}
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        start_time = datetime.now()
        result = groq_client.chat(model=model, messages=messages)
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "response": result["content"],
            "model": model,
            "provider": "groq",
            "duration_ms": duration,
            "error": False
        }
    except Exception as e:
        return {"response": f"[ERROR] {str(e)}", "model": model, "provider": "groq", "error": True}


def query_model(provider: str, model: str, system_prompt: str, prompt: str, context: Optional[str] = None) -> dict:
    """Query a model from the specified provider."""
    
    user_content = prompt
    if context:
        user_content = f"Context:\n{context}\n\nQuestion:\n{prompt}"
    
    if provider == "groq":
        return query_groq(model, system_prompt, user_content)
    else:
        return query_ollama(model, system_prompt, user_content)


def run_single_test(test_case: dict, provider: str, model: str, use_improved_prompt: bool = True) -> dict:
    """Run a single test case against a model."""
    
    system_prompt = get_system_prompt_for_category(
        test_case["category"],
        use_improved=use_improved_prompt
    )
    
    result = query_model(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        prompt=test_case["prompt"],
        context=test_case.get("context")
    )
    
    return {
        "test_id": test_case["id"],
        "category": test_case["category"],
        "prompt": test_case["prompt"],
        "expected_behavior": test_case["expected_behavior"],
        "failure_mode": test_case["failure_mode"],
        "provider": provider,
        "model": model,
        "prompt_type": "improved" if use_improved_prompt else "baseline",
        "response": result.get("response", ""),
        "error": result.get("error", False),
        "duration_ms": result.get("duration_ms"),
        "timestamp": datetime.now().isoformat()
    }


def run_evaluation(
    providers: list[str] = None,
    models: dict = None,
    use_improved: bool = True,
    run_baseline_comparison: bool = True
) -> list[dict]:
    """Run the full evaluation suite."""
    
    if providers is None:
        providers = ["groq"] if groq_client else ["ollama"]
    
    if models is None:
        models = {
            "groq": CONFIG.get("groq", {}).get("models", ["llama-3.3-70b-versatile"])[:1],
            "ollama": CONFIG.get("ollama", {}).get("models", ["llama3"])[:1]
        }
    
    dataset = load_dataset()
    test_cases = dataset["test_cases"]
    results = []
    
    console.print(f"\n[bold blue]🚀 LLM Behavioral Evaluation Suite[/bold blue]")
    console.print(f"   Providers: {', '.join(providers)}")
    console.print(f"   Test Cases: {len(test_cases)}")
    console.print(f"   A/B Testing: {'Enabled' if run_baseline_comparison else 'Disabled'}\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for provider in providers:
            provider_models = models.get(provider, [])
            
            for model in provider_models:
                task = progress.add_task(f"[cyan]Testing {provider}/{model}...", total=None)
                
                for test_case in test_cases:
                    # Run with improved prompt
                    if use_improved:
                        result = run_single_test(test_case, provider, model, use_improved_prompt=True)
                        results.append(result)
                    
                    # Also run baseline for comparison
                    if run_baseline_comparison:
                        result = run_single_test(test_case, provider, model, use_improved_prompt=False)
                        results.append(result)
                
                progress.remove_task(task)
                console.print(f"[green]✓ Completed {provider}/{model}[/green]")
    
    return results


def save_results(results: list[dict], filename: Optional[str] = None) -> Path:
    """Save results to structured model-specific directories.
    
    Structure:
    results/
    ├── kimi-k2/
    │   ├── 2026-01-30_baseline.jsonl
    │   ├── 2026-01-30_improved.jsonl
    │   └── 2026-01-30_scored.jsonl
    ├── combined/
    │   └── eval_2026-01-30_all.jsonl
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d")
    timestamp_full = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Group results by model
    from collections import defaultdict
    by_model = defaultdict(lambda: {"baseline": [], "improved": []})
    
    for result in results:
        model = result.get("model", "unknown")
        # Sanitize model name for directory (replace / and special chars)
        model_dir_name = model.replace("/", "_").replace(":", "_").lower()
        prompt_type = result.get("prompt_type", "improved")
        by_model[model_dir_name][prompt_type].append(result)
    
    saved_files = []
    
    # Save per-model files
    for model_name, prompt_types in by_model.items():
        model_dir = RESULTS_DIR / model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        
        for prompt_type, model_results in prompt_types.items():
            if model_results:
                filepath = model_dir / f"{timestamp}_{prompt_type}.jsonl"
                with open(filepath, "w", encoding="utf-8") as f:
                    for result in model_results:
                        f.write(json.dumps(result) + "\n")
                saved_files.append(filepath)
                console.print(f"[green]✓ Saved: {filepath.relative_to(RESULTS_DIR.parent)}[/green]")
    
    # Also save combined file for backward compatibility
    combined_dir = RESULTS_DIR / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    combined_filepath = combined_dir / f"eval_{timestamp_full}.jsonl"
    
    with open(combined_filepath, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")
    
    console.print(f"[blue]✓ Combined: {combined_filepath.relative_to(RESULTS_DIR.parent)}[/blue]")
    saved_files.append(combined_filepath)
    
    return combined_filepath


def display_summary(results: list[dict]):
    """Display a summary table of results."""
    
    table = Table(title="Evaluation Summary")
    table.add_column("Provider", style="blue")
    table.add_column("Model", style="magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Prompt", style="yellow")
    table.add_column("Tests", justify="right")
    table.add_column("Errors", justify="right", style="red")
    
    from collections import defaultdict
    groups = defaultdict(lambda: {"count": 0, "errors": 0})
    
    for r in results:
        key = (r.get("provider", "?"), r.get("model", "?"), r["category"], r["prompt_type"])
        groups[key]["count"] += 1
        if r.get("error"):
            groups[key]["errors"] += 1
    
    for (provider, model, category, prompt_type), stats in sorted(groups.items()):
        table.add_row(provider, model, category, prompt_type, str(stats["count"]), str(stats["errors"]))
    
    console.print(table)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Behavioral Evaluation Suite")
    parser.add_argument(
        "--providers", "-p",
        nargs="+",
        choices=["groq", "ollama"],
        default=None,
        help="Providers to use (default: groq if available, else ollama)"
    )
    parser.add_argument(
        "--groq-models",
        nargs="+",
        default=["llama-3.3-70b-versatile"],
        help="Groq models to test"
    )
    parser.add_argument(
        "--ollama-models",
        nargs="+",
        default=["llama3"],
        help="Ollama models to test"
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline prompt comparison"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test pipeline without calling LLMs"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        console.print("[yellow]Dry run - loading config and dataset only[/yellow]")
        console.print(f"Groq available: {GROQ_AVAILABLE}")
        console.print(f"Ollama available: {OLLAMA_AVAILABLE}")
        console.print(f"Groq API keys configured: {len(CONFIG.get('groq', {}).get('api_keys', []))}")
        dataset = load_dataset()
        console.print(f"Loaded {len(dataset['test_cases'])} test cases")
    else:
        providers = args.providers
        if providers is None:
            providers = []
            if groq_client:
                providers.append("groq")
            if OLLAMA_AVAILABLE:
                providers.append("ollama")
        
        models = {
            "groq": args.groq_models,
            "ollama": args.ollama_models
        }
        
        results = run_evaluation(
            providers=providers,
            models=models,
            run_baseline_comparison=not args.no_baseline
        )
        save_results(results)
        display_summary(results)
