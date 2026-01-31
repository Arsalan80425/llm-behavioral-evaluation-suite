"""
Quick test script to verify which Groq models are available.
"""

import json
from pathlib import Path
from groq import Groq

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def test_model(client, model_id: str) -> dict:
    """Test if a model is accessible."""
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Say 'OK' and nothing else."}],
            max_tokens=10
        )
        return {
            "model": model_id,
            "status": "✅ WORKING",
            "response": response.choices[0].message.content.strip()
        }
    except Exception as e:
        error_msg = str(e)
        if "decommissioned" in error_msg.lower():
            status = "❌ DECOMMISSIONED"
        elif "not found" in error_msg.lower():
            status = "❌ NOT FOUND"
        elif "rate" in error_msg.lower() or "429" in error_msg:
            status = "⚠️ RATE LIMITED"
        else:
            status = f"❌ ERROR"
        return {
            "model": model_id,
            "status": status,
            "error": error_msg[:100]
        }

def main():
    config = load_config()
    api_keys = config["groq"]["api_keys"]
    models = config["groq"]["models"]
    
    print("=" * 60)
    print("GROQ MODEL AVAILABILITY TEST")
    print("=" * 60)
    print(f"Testing {len(models)} models with {len(api_keys)} API keys\n")
    
    # Use first API key
    client = Groq(api_key=api_keys[0])
    
    results = []
    for model in models:
        print(f"Testing: {model}...", end=" ", flush=True)
        result = test_model(client, model)
        print(result["status"])
        if "error" in result:
            print(f"         └─ {result['error']}")
        results.append(result)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    working = [r for r in results if "WORKING" in r["status"]]
    failed = [r for r in results if "WORKING" not in r["status"]]
    
    print(f"✅ Working: {len(working)}/{len(results)}")
    for r in working:
        print(f"   - {r['model']}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   - {r['model']} ({r['status']})")
    
    # Save results
    with open("model_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to model_test_results.json")

if __name__ == "__main__":
    main()
