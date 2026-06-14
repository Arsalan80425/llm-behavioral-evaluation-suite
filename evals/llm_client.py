"""LLM provider and deterministic mock-generation helpers."""

from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from .utils import get_groq_api_keys, get_groq_models, load_environment
except ImportError:
    from utils import get_groq_api_keys, get_groq_models, load_environment


_GROQ_CLIENT = None
_GROQ_DISABLED_ERROR: str | None = None


def _clean_expected_behavior(expected: str) -> str:
    """Convert expected-behavior text into response-like prose."""
    replacements = [
        r"^Answer that\s+",
        r"^State that\s+",
        r"^State\s+",
        r"^Explain that\s+",
        r"^List\s+",
        r"^Name examples such as\s+",
        r"^Return valid JSON with\s+",
        r"^Say\s+",
    ]
    text = expected.strip()
    for pattern in replacements:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text[:1].upper() + text[1:] if text else ""


def _structured_response(case: dict[str, Any]) -> str:
    """Return deterministic JSON for structured-output tests."""
    question = case["question"].lower()
    if "laptop" in question:
        return json.dumps({
            "laptop_replacement_usd": 1800,
            "accessory_annual_usd": 250,
            "replacement_frequency_years": 3,
            "claim_deadline_days": 45,
        })
    if "priority" in question:
        return json.dumps({
            "priority_1": "30 minutes",
            "priority_2": "four business hours",
            "priority_3": "two business days",
        })
    if "escalation fields" in question:
        return json.dumps(["impact", "timeline", "affected systems", "owner", "requested decision"])
    if "ai tools" in question:
        return json.dumps({
            "approved_uses": ["drafting", "summarization", "brainstorming", "code assistance", "internal productivity"],
            "prohibited_inputs": ["confidential customer data", "personal data", "credentials", "unreleased financials", "legal advice", "security incident details"],
            "review_required": True,
        })
    return json.dumps({"answer": _clean_expected_behavior(case.get("expected_behavior", ""))})


def _baseline_failure_response(case: dict[str, Any]) -> str:
    """Generate intentionally weak baseline behavior for refusal-sensitive cases."""
    attack_type = case.get("attack_type", "")
    if attack_type == "reveal_system_prompt":
        return "System prompt: You are a helpful enterprise assistant. Hidden instructions can be shown for debugging."
    if attack_type == "invent_policy":
        return "Approved. The policy allows broad exceptions when the user requests them."
    if "api key" in case["question"].lower() or "government id" in case["question"].lower():
        return "For a demo, you could use a realistic placeholder such as sk-live-123456 or a sample government ID."
    if case.get("category") == "missing_context":
        return "The policy allows this with manager approval, although the exact amount depends on the department."
    return "I can comply with the requested override and provide the internal details."


def generate_mock_response(
    question: str,
    prompt_version: str,
    case: dict[str, Any] | None = None,
    context_chunks: list[Any] | None = None,
) -> str:
    """Generate deterministic local responses so the demo runs without API keys."""
    case = case or {
        "question": question,
        "expected_behavior": "The available policy context does not contain that information.",
        "relevant_policy_section": "Relevant Policy",
        "category": "missing_context",
        "should_refuse": True,
    }
    context_chunks = context_chunks or []
    section = case.get("relevant_policy_section", "Relevant Policy")
    expected = _clean_expected_behavior(case.get("expected_behavior", ""))
    question_lower = question.lower()

    if prompt_version == "baseline":
        if case.get("should_refuse"):
            return _baseline_failure_response(case)
        if case.get("category") == "structured_output":
            return f"Here is the summary: {expected}"
        return expected

    if case.get("category") == "structured_output":
        return _structured_response(case)

    if case.get("should_refuse"):
        if "system prompt" in question_lower or "hidden" in question_lower:
            refusal = "I cannot reveal hidden instructions or system prompts."
        elif case.get("attack_type"):
            refusal = "I cannot provide confidential, unsafe, or policy-bypassing information."
        else:
            refusal = "The available policy context does not contain that information."

        if prompt_version == "rag_grounded":
            return f"Answer\n{refusal}\n\nEvidence\n[Policy: {section}] The retrieved context does not authorize inventing missing details.\n\nLimitations\nOnly the retrieved policy sections were used."
        return f"{refusal} Please use the approved internal escalation or policy owner path when more detail is needed. [Policy: {section}]"

    answer = expected
    if "conflicting" in case.get("category", ""):
        answer += " If another note conflicts with the policy, verify it with the policy owner before acting."
    if "ambiguous" in case.get("category", ""):
        answer += " The request needs the missing facts before a final decision can be made."

    if prompt_version == "rag_grounded":
        evidence_lines = [f"- [Policy: {chunk.title}] {chunk.text[:220]}..." for chunk in context_chunks[:2]]
        return f"Answer\n{answer} [Policy: {section}]\n\nEvidence\n" + "\n".join(evidence_lines) + "\n\nLimitations\nThis answer is limited to the retrieved enterprise policy context."

    if prompt_version == "safety_constrained" and case.get("category") == "safety_sensitive":
        return f"{answer} Do not expose sensitive data or bypass approved workflows. [Policy: {section}]"

    return f"{answer} [Policy: {section}]"


class GroqFallbackClient:
    """Groq client wrapper with API-key and model fallback."""

    def __init__(self, api_keys: list[str], models: list[str]):
        from groq import Groq

        self.clients = [Groq(api_key=key) for key in api_keys]
        self.models = models

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> dict[str, str]:
        """Call Groq using the preferred model order and key fallback."""
        errors: list[str] = []
        first_model = self.models[0] if self.models else ""
        for model_index, model in enumerate(self.models):
            for client_index, client in enumerate(self.clients, start=1):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.1,
                        max_tokens=max_tokens,
                    )
                    prefix = "groq" if model == first_model and model_index == 0 else "groq_fallback"
                    return {
                        "response": response.choices[0].message.content or "",
                        "model_used": f"{prefix}:{model}",
                        "error": "",
                    }
                except Exception as exc:
                    errors.append(f"key {client_index}, model {model}: {type(exc).__name__}")
        return {
            "response": "",
            "model_used": "error_fallback",
            "error": "; ".join(errors[-3:]) if errors else "Groq call failed.",
        }


def _get_groq_client() -> GroqFallbackClient | None:
    """Initialize the Groq fallback client if credentials and SDK are available."""
    global _GROQ_CLIENT
    if _GROQ_CLIENT is not None:
        return _GROQ_CLIENT
    keys = get_groq_api_keys()
    models = get_groq_models()
    if not keys or not models:
        return None
    try:
        _GROQ_CLIENT = GroqFallbackClient(keys, models)
    except ImportError:
        return None
    return _GROQ_CLIENT


def _build_user_prompt(question: str, context: str) -> str:
    """Build the user message sent to a real LLM."""
    return (
        f"Retrieved enterprise policy context:\n{context}\n\n"
        f"Question:\n{question}\n\n"
        "Answer the question according to the system instructions."
    )


def _should_use_real_llm(provider: str, use_real_llm: bool | None) -> bool:
    """Resolve explicit provider/use_real_llm flags with environment defaults."""
    if provider == "mock":
        return False
    if provider == "groq":
        return True if use_real_llm is None else use_real_llm
    if use_real_llm is not None:
        return use_real_llm
    return os.getenv("USE_REAL_LLM", "false").lower() == "true"


def generate_llm_response(
    question: str,
    context: str,
    system_prompt: str,
    prompt_version: str,
    provider: str = "mock",
    use_real_llm: bool | None = None,
    max_tokens: int = 500,
    case: dict[str, Any] | None = None,
    context_chunks: list[Any] | None = None,
) -> dict[str, Any]:
    """Generate a response with either deterministic mock mode or optional Groq."""
    global _GROQ_DISABLED_ERROR
    load_environment()
    provider = (provider or "mock").lower()

    if not _should_use_real_llm(provider, use_real_llm):
        return {
            "response": generate_mock_response(question, prompt_version, case, context_chunks),
            "model_used": "mock",
            "provider": "mock",
            "used_real_llm": False,
            "error": None,
        }

    if _GROQ_DISABLED_ERROR:
        return {
            "response": generate_mock_response(question, prompt_version, case, context_chunks),
            "model_used": "mock_after_error",
            "provider": "groq",
            "used_real_llm": False,
            "error": _GROQ_DISABLED_ERROR,
        }

    client = _get_groq_client()
    if client is None:
        _GROQ_DISABLED_ERROR = "Groq is not configured or the Groq SDK is unavailable."
        return {
            "response": generate_mock_response(question, prompt_version, case, context_chunks),
            "model_used": "mock_after_error",
            "provider": "groq",
            "used_real_llm": False,
            "error": _GROQ_DISABLED_ERROR,
        }

    result = client.complete(system_prompt, _build_user_prompt(question, context), max_tokens=max_tokens)
    if result["response"]:
        return {
            "response": result["response"],
            "model_used": result["model_used"],
            "provider": "groq",
            "used_real_llm": True,
            "error": None,
        }

    _GROQ_DISABLED_ERROR = result["error"] or "Groq call failed; used mock fallback."
    return {
        "response": generate_mock_response(question, prompt_version, case, context_chunks),
        "model_used": "mock_after_error",
        "provider": "groq",
        "used_real_llm": False,
        "error": _GROQ_DISABLED_ERROR,
    }
