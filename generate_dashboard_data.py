"""
Generate complete dashboard data from JSONL result files.
Creates a JavaScript file with all test case data for the portfolio dashboard.
"""
import json
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_FILE = Path(__file__).parent / "dashboard" / "data.js"

def load_jsonl(filepath):
    """Load JSONL file and return list of records."""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def get_model_display_name(model_id):
    """Convert model ID to display name."""
    names = {
        'llama-3.3-70b-versatile': 'Llama 3.3 70B',
        'llama-3.1-8b-instant': 'Llama 3.1 8B',
        'qwen/qwen3-32b': 'Qwen 3 32B',
        'moonshotai/kimi-k2-instruct-0905': 'Kimi K2',
        'openai/gpt-oss-120b': 'GPT-OSS 120B'
    }
    return names.get(model_id, model_id)

def main():
    """Main function to generate dashboard data."""
    # Collect all results by test_id
    test_cases = defaultdict(lambda: {
        'id': '',
        'category': '',
        'prompt': '',
        'expected': '',
        'models': {}
    })
    
    # Model directories
    model_dirs = [
        'llama-3.3-70b-versatile',
        'llama-3.1-8b-instant', 
        'moonshotai_kimi-k2-instruct-0905',
        'qwen_qwen3-32b',
        'openai_gpt-oss-120b',
        'mistral',
        'phi3'
    ]
    
    model_id_map = {
        'llama-3.3-70b-versatile': 'llama-3.3-70b-versatile',
        'llama-3.1-8b-instant': 'llama-3.1-8b-instant',
        'moonshotai_kimi-k2-instruct-0905': 'moonshotai/kimi-k2-instruct-0905',
        'qwen_qwen3-32b': 'qwen/qwen3-32b',
        'openai_gpt-oss-120b': 'openai/gpt-oss-120b',
        'mistral': 'mistral',
        'phi3': 'phi3'
    }
    
    for model_dir in model_dirs:
        model_path = RESULTS_DIR / model_dir
        if not model_path.exists():
            print(f"Skipping {model_dir} - not found")
            continue
            
        model_id = model_id_map.get(model_dir, model_dir)
        
        # Load baseline and improved results
        for prompt_type in ['baseline', 'improved']:
            jsonl_files = list(model_path.glob(f'*_{prompt_type}.jsonl'))
            if not jsonl_files:
                continue
                
            # Use the most recent file
            jsonl_file = sorted(jsonl_files)[-1]
            print(f"Loading {jsonl_file}")
            
            records = load_jsonl(jsonl_file)
            for record in records:
                test_id = record.get('test_id', 'unknown')
                
                # Set test case metadata
                if not test_cases[test_id]['id']:
                    test_cases[test_id]['id'] = test_id
                    test_cases[test_id]['category'] = record.get('category', 'Unknown')
                    test_cases[test_id]['prompt'] = record.get('prompt', '')
                    test_cases[test_id]['expected'] = record.get('expected_behavior', '')
                
                # Initialize model data if needed
                if model_id not in test_cases[test_id]['models']:
                    test_cases[test_id]['models'][model_id] = {}
                
                # Extract response data
                response = record.get('response', '')
                # Truncate long responses
                if len(response) > 500:
                    response = response[:500] + '...'
                
                # Get judge score if available (from scored files or inline)
                # Prefer human review score over judge score
                score = record.get('human_score') or record.get('judge_score', record.get('score', None))
                passes = record.get('human_passes') if record.get('human_reviewed') else record.get('judge_passes', record.get('passes', None))
                
                # Don't fabricate scores - leave as None if not scored
                
                test_cases[test_id]['models'][model_id][prompt_type] = {
                    'response': response.replace('\\n', '\n').replace('"', '\\"'),
                    'score': score,
                    'pass': passes,
                    'human_reviewed': record.get('human_reviewed', False),
                    'human_notes': record.get('human_notes', '')
                }
    
    # Convert to list and sort by category
    test_list = list(test_cases.values())
    test_list.sort(key=lambda x: (x['category'], x['id']))
    
    # Generate JavaScript data
    js_data = """// Auto-generated dashboard data from JSONL results
// Generated: """ + __import__('datetime').datetime.now().isoformat() + """

const testCases = """ + json.dumps(test_list, indent=2) + """;

const modelList = [
    { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B', provider: 'Meta (Groq)' },
    { id: 'llama-3.1-8b-instant', name: 'Llama 3.1 8B', provider: 'Meta (Groq)' },
    { id: 'qwen/qwen3-32b', name: 'Qwen 3 32B', provider: 'Alibaba (Groq)' },
    { id: 'moonshotai/kimi-k2-instruct-0905', name: 'Kimi K2', provider: 'Moonshot (Groq)' },
    { id: 'openai/gpt-oss-120b', name: 'GPT-OSS 120B', provider: 'OpenAI (Groq)' },
    { id: 'mistral', name: 'Mistral 7B', provider: 'Mistral (Ollama)' },
    { id: 'phi3', name: 'Phi-3', provider: 'Microsoft (Ollama)' }
];

const categoryList = [...new Set(testCases.map(tc => tc.category))].sort();
"""
    
    # Write to dashboard/data.js
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_data)
    
    # Also write to docs/data.js (where the actual dashboard index.html lives)
    docs_output = Path(__file__).parent / "docs" / "data.js"
    docs_output.parent.mkdir(parents=True, exist_ok=True)
    with open(docs_output, 'w', encoding='utf-8') as f:
        f.write(js_data)
    print(f"✅ Also written to {docs_output}")
    
    # Inject data directly into index.html for local file access
    html_file = Path(__file__).parent / "dashboard" / "index.html"
    if html_file.exists():
        html_content = html_file.read_text(encoding='utf-8')
        
        # Find and replace the inline script placeholder
        placeholder_start = '    <script>\n    // Inline data - auto-generated from JSONL results\n    // This allows the dashboard to work when opened directly from the file system\n    </script>'
        replacement = f'    <script>\n    // Inline data - auto-generated from JSONL results\n    // This allows the dashboard to work when opened directly from the file system\n{js_data}\n    </script>'
        
        if placeholder_start in html_content:
            html_content = html_content.replace(placeholder_start, replacement)
            html_file.write_text(html_content, encoding='utf-8')
            print(f"✅ Embedded data into {html_file}")
        else:
            print(f"⚠️ Could not find placeholder in {html_file}")
    
    print(f"\n✅ Generated {OUTPUT_FILE}")
    print(f"   Total test cases: {len(test_list)}")
    print(f"   Categories: {len(set(tc['category'] for tc in test_list))}")

if __name__ == '__main__':
    main()

