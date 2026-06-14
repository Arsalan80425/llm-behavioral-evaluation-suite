"""Shared file and configuration utilities for evaluation scripts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT_DIR / "prompts"
DATASETS_DIR = ROOT_DIR / "datasets"
RESULTS_DIR = ROOT_DIR / "results"

PROMPT_FILES = {
    "baseline": "baseline_prompt.md",
    "optimized": "optimized_prompt.md",
    "safety_constrained": "safety_constrained_prompt.md",
    "rag_grounded": "rag_grounded_prompt.md",
}

DEFAULT_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


def load_environment() -> None:
    """Load optional environment variables from .env if present."""
    load_dotenv(ROOT_DIR / ".env")


def load_ignored_config() -> dict:
    """Load optional ignored config.json without requiring it in fresh installs."""
    config_path = ROOT_DIR / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_groq_api_keys() -> list[str]:
    """Return Groq API keys from .env first, then ignored config.json."""
    env_keys: list[str] = []

    comma_separated = os.getenv("GROQ_API_KEYS", "")
    if comma_separated:
        env_keys.extend(key.strip() for key in comma_separated.split(","))

    for name in ["GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                  "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6"]:
        value = os.getenv(name, "").strip()
        if value:
            env_keys.append(value)

    keys = env_keys
    if not keys:
        config = load_ignored_config()
        keys = config.get("groq", {}).get("api_keys", [])

    deduped: list[str] = []
    seen = set()
    for key in keys:
        if not key or key.startswith("YOUR_") or key in seen:
            continue
        deduped.append(key)
        seen.add(key)
    return deduped


def get_groq_models() -> list[str]:
    """Return Groq model preference order from env/config/defaults."""
    models: list[str] = []
    primary = os.getenv("GROQ_MODEL", "").strip()
    if primary:
        models.append(primary)

    fallbacks = os.getenv("GROQ_FALLBACK_MODELS", "")
    if fallbacks:
        models.extend(model.strip() for model in fallbacks.split(","))

    if not models:
        models.extend(DEFAULT_GROQ_MODELS)

    deduped: list[str] = []
    seen = set()
    for model in models:
        if model and model not in seen:
            deduped.append(model)
            seen.add(model)
    return deduped


def ensure_results_dir() -> Path:
    """Create and return the results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def read_text(path: Path) -> str:
    """Read a UTF-8 text file and return an empty string if it is missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_prompt_versions() -> dict[str, str]:
    """Load all prompt versions from prompts/."""
    return {name: read_text(PROMPTS_DIR / filename) for name, filename in PROMPT_FILES.items()}


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL records from a file, skipping empty lines."""
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} at line {line_no}: {exc}") from exc
    return records


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    """Write records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_section(path: Path, title: str, content: str) -> None:
    """Append or create a markdown report section."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_text(path)
    marker = f"## {title}"
    new_section = f"{marker}\n\n{content.strip()}\n\n"
    if marker in existing:
        pattern = re.compile(rf"^## {re.escape(title)}\n.*?(?=^## |\Z)", flags=re.MULTILINE | re.DOTALL)
        updated = pattern.sub(new_section.rstrip() + "\n\n", existing).rstrip() + "\n"
        path.write_text(updated, encoding="utf-8")
    else:
        prefix = existing.rstrip() + "\n\n" if existing else ""
        path.write_text(prefix + new_section, encoding="utf-8")


def safe_mean(values: Iterable[float]) -> float:
    """Return the arithmetic mean, or 0.0 for an empty iterable."""
    values = [float(value) for value in values]
    return sum(values) / len(values) if values else 0.0
