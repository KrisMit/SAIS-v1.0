"""
LOCAL MISSION DOCUMENTATION AGENT
Uses Ollama (llama3.2:1b) to answer questions about mission docs.
Completely offline — no internet required.
"""

import json
import datetime
import os
import sys
import socket
import urllib.request
import urllib.error
from pathlib import Path

socket.setdefaulttimeout(None)

MODEL        = "llama3.2:1b"
OLLAMA_URL   = "http://localhost:11434/api/generate"
DOC_DIR      = "mission_docs"
LOG_FILE     = "agent_local_session_log.jsonl"

def load_documents():
    """Load all .txt and .md files from mission_docs folder"""
    docs = {}
    doc_path = Path(DOC_DIR)
    
    if not doc_path.exists():
        print(f"⚠ Folder '{DOC_DIR}' not found")
        print("  Create it and add mission documentation files")
        sys.exit(1)
    
    for file in sorted(doc_path.glob("*.txt")) + sorted(doc_path.glob("*.md")):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            docs[file.name] = content
            print(f"✓ Loaded: {file.name} ({len(content)} chars)")
        except Exception as e:
            print(f"⚠ Error reading {file.name}: {e}")
    
    if not docs:
        print(f"⚠ No .txt or .md files found in {DOC_DIR}/")
        sys.exit(1)
    
    return docs

def build_context(docs, max_chars=3000):
    """Build context, truncating if needed to fit in context window"""
    context = ""
    remaining = max_chars
    
    priority_docs = [d for d in docs.keys() if 'emergency' in d.lower() or 'procedure' in d.lower()]
    other_docs = [d for d in docs.keys() if d not in priority_docs]
    ordered = priority_docs + other_docs
    
    for filename in ordered:
        content = docs[filename]
        snippet = content[:remaining] if len(content) > remaining else content
        context += f"## {filename}\n{snippet}\n\n"
        remaining -= len(snippet)
        if remaining < 200:
            context += "\n[Context window limit reached]\n"
            break
    
    return context

def ask_ollama(question, context):
    """Query local LLM with document context"""
    
    prompt = f"""Based on this mission documentation, answer the question.

MISSION DOCUMENTATION:
{context}

QUESTION: {question}

ANSWER (based only on the documentation above):"""
    
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.1,
            "num_predict": 200,
            "top_p": 0.9,
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    full_response = ""
    try:
        print("\n🤖 Agent thinking...")
        print()
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        token = chunk.get('response', '')
                        print(token, end='', flush=True)
                        full_response += token
                        if chunk.get('done', False):
                            break
                    except json.JSONDecodeError:
                        continue
        print()
        print()
        return full_response.strip()
    
    except urllib.error.URLError as e:
        msg = f"Cannot reach Ollama. Make sure it's running."
        print(f"\n⚠ {msg}")
        return f"[Error: {msg}]"
    except Exception as e:
        msg = str(e)
        print(f"\n⚠ Error: {msg}")
        return f"[Error: {msg}]"

def check_ollama():
    """Verify Ollama is running"""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags") as resp:
            data = json.loads(resp.read())
            models = [m['name'] for m in data.get('models', [])]
            if any(MODEL.split(':')[0] in m for m in models):
                print(f"✓ Ollama running · {MODEL} available")
                return True
            else:
                print(f"⚠ Ollama running but {MODEL} not found")
                return False
    except Exception:
        print("⚠ Ollama not responding at localhost:11434")
        print("  Start it: ollama serve")
        return False

def run_agent(docs):
    """Multi-turn agent conversation"""
    print()
    print("=" * 56)
    print("  LOCAL MISSION DOCUMENTATION AGENT")
    print("  Offline Mode · Expedition Olympus")
    print("=" * 56)
    print()
    print("Ask questions about mission procedures and documentation.")
    print("Commands: 'docs'  'exit'")
    print("-" * 56)
    
    context = build_context(docs)
    interaction_count = 0
    
    while True:
        print()
        question = input("YOU: ").strip()
        
        if not question:
            continue
        
        if question.lower() == 'exit':
            print(f"\nSession ended. {interaction_count} interactions logged.")
            break
        
        if question.lower() == 'docs':
            print("\nLoaded documentation:")
            for doc in docs.keys():
                print(f"  • {doc}")
            continue
        
        response = ask_ollama(question, context)
        
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'interaction': interaction_count + 1,
            'question': question,
            'response': response,
            'response_words': len(response.split()),
        }
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        interaction_count += 1
        print(f"[Logged · {log_entry['response_words']} words]")

if __name__ == "__main__":
    print("\n" + "=" * 56)
    print("  LOCAL MISSION AGENT")
    print("=" * 56 + "\n")
    
    docs = load_documents()
    total_chars = sum(len(c) for c in docs.values())
    print(f"\n✓ Loaded {len(docs)} documents ({total_chars:,} chars)")
    
    print()
    if not check_ollama():
        ans = input("\nContinue anyway? (y/n): ").strip().lower()
        if ans != 'y':
            sys.exit(0)
    
    run_agent(docs)