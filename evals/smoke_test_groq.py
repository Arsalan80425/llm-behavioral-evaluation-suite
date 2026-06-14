"""Smoke test script to verify optional Groq connectivity."""

import os
import sys

# Import from local modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from evals.llm_client import generate_llm_response
from evals.utils import get_groq_api_keys, get_groq_models, load_environment

def main():
    print("Running Groq smoke test...")
    load_environment()

    keys = get_groq_api_keys()
    models = get_groq_models()

    has_key = len(keys) > 0
    print(f"GROQ_API_KEY found: {has_key}")

    selected_model = models[0] if models else "None"
    print(f"Selected GROQ_MODEL: {selected_model}")

    # Send exactly one tiny test question with a tiny context.
    question = "What is the capital of France?"
    context = "France is a country in Europe. Its capital is Paris."
    system_prompt = "You are a helpful assistant."
    prompt_version = "baseline"

    print("Sending a single test request to Groq...")
    result = generate_llm_response(
        question=question,
        context=context,
        system_prompt=system_prompt,
        prompt_version=prompt_version,
        provider="groq",
        use_real_llm=True, # force a single real Groq call safely
        max_tokens=50,
    )

    model_used = result.get("model_used", "")
    used_real_llm = result.get("used_real_llm", False)
    error = result.get("error")

    print(f"model_used: {model_used}")
    print(f"used_real_llm: {used_real_llm}")
    # Improve error visibility
    if error:
        # Provide a sanitized short error message to diagnose common issues
        error_lower = error.lower()
        if "authentication" in error_lower or "401" in error_lower:
            clean_error = "Authentication failure: Please check your GROQ_API_KEY."
        elif "rate limit" in error_lower or "429" in error_lower:
            clean_error = "Rate limit exceeded: You may be out of free tier quota."
        elif "invalid model" in error_lower or "not found" in error_lower or "404" in error_lower:
            clean_error = f"Invalid or unavailable model: {selected_model} might not be available."
        elif "connection" in error_lower or "network" in error_lower or "timeout" in error_lower:
            clean_error = "Network/API connection issue: Unable to reach Groq API."
        elif "sdk" in error_lower:
            clean_error = "Missing SDK: Ensure the groq python package is installed."
        else:
            clean_error = f"API Error: {error}"
            
        print(f"error: {clean_error}")
    else:
        print("error: None")

    response_text = result.get("response", "")
    print(f"Response (first 300 chars): {response_text[:300]}")

    if used_real_llm and model_used.startswith("groq:"):
        print("\nSmoke test PASSED.")
        sys.exit(0)
    else:
        print("\nSmoke test FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
