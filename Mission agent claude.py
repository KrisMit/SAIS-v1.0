"""
MISSION DOCUMENTATION AGENT
Uses Claude API to intelligently answer questions about mission docs.
For pre-mission planning and document review.

Requires: pip install anthropic
Get API key from claude.ai/account/api-keys
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

try:
    from anthropic import Anthropic
except ImportError:
    print("Error: Install with: pip install anthropic")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("⚠ ANTHROPIC_API_KEY not set")
    print("  Get key from: https://claude.ai/account/api-keys")
    print("  Then run: export ANTHROPIC_API_KEY=sk-...")
    sys.exit(1)

DOC_DIR = "mission_docs"
LOG_FILE = "agent_session_log.jsonl"

# ─────────────────────────────────────────────────────────────
# LOAD MISSION DOCUMENTS
# ─────────────────────────────────────────────────────────────
def load_documents():
    """Load all .txt and .md files from mission_docs folder"""
    docs = {}
    doc_path = Path(DOC_DIR)
    
    if not doc_path.exists():
        print(f"⚠ Folder '{DOC_DIR}' not found")
        print("  Create it and add mission documentation:")
        print("    - mission_manual.txt")
        print("    - emergency_procedures.txt")
        print("    - any other .txt or .md files")
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

# ─────────────────────────────────────────────────────────────
# BUILD CONTEXT FROM DOCUMENTS
# ─────────────────────────────────────────────────────────────
def build_context(docs):
    """Combine all documents into context for Claude"""
    context = "# MISSION DOCUMENTATION CONTEXT\n\n"
    for filename, content in docs.items():
        context += f"## {filename}\n{content}\n\n"
    return context

# ─────────────────────────────────────────────────────────────
# CREATE AGENT SESSION
# ─────────────────────────────────────────────────────────────
def create_agent(docs):
    """Initialize Claude client with multi-turn conversation"""
    client = Anthropic()
    context = build_context(docs)
    
    system_prompt = f"""You are an intelligent mission documentation assistant for Expedition Olympus (AATC).

You have access to all mission documentation:
{list(docs.keys())}

Your role:
1. Answer questions about mission procedures, emergencies, equipment, and protocols
2. Provide accurate information ONLY from the documentation provided
3. If information is not in the docs, clearly state: "This is not covered in the mission documentation"
4. For emergency questions, prioritize safety and clarity
5. Reference specific procedures by name (e.g., "E-004 Power Outage")
6. For complex questions, break down the answer into numbered steps

MISSION DOCUMENTATION:
{context}

Answer all questions based ONLY on this documentation. Be precise, helpful, and safety-focused."""

    return client, system_prompt

# ─────────────────────────────────────────────────────────────
# AGENT CONVERSATION LOOP
# ─────────────────────────────────────────────────────────────
def run_agent(client, system_prompt):
    """Multi-turn conversation with Claude about mission docs"""
    print()
    print("=" * 56)
    print("  MISSION DOCUMENTATION AGENT")
    print("  Expedition Olympus · AATC")
    print("=" * 56)
    print()
    print("Ask any question about mission procedures, equipment,")
    print("emergencies, protocols, or documentation.")
    print()
    print("Commands: 'docs'  'history'  'exit'")
    print("-" * 56)
    
    conversation_history = []
    interaction_count = 0
    
    while True:
        print()
        question = input("YOU: ").strip()
        
        if not question:
            continue
        
        # Commands
        if question.lower() == 'exit':
            print(f"\nSession ended. {interaction_count} interactions logged.")
            break
        
        if question.lower() == 'docs':
            print("\nLoaded documentation:")
            for doc in docs.keys():
                print(f"  • {doc}")
            continue
        
        if question.lower() == 'history':
            if conversation_history:
                print(f"\nConversation history ({len(conversation_history)} messages):")
                for i, msg in enumerate(conversation_history, 1):
                    role = msg['role'].upper()
                    text = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
                    print(f"  {i}. {role}: {text}")
            else:
                print("\nNo conversation history yet.")
            continue
        
        # Add user message to history
        conversation_history.append({
            "role": "user",
            "content": question
        })
        
        # Get Claude's response
        print("\n🤖 Agent thinking...")
        try:
            response = client.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=1500,
                system=system_prompt,
                messages=conversation_history
            )
            
            answer = response.content[0].text
            
            # Add assistant response to history
            conversation_history.append({
                "role": "assistant",
                "content": answer
            })
            
            # Display answer
            print()
            print("AGENT RESPONSE:")
            print("-" * 40)
            print(answer)
            print("-" * 40)
            
            # Log interaction
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'interaction': interaction_count + 1,
                'user_question': question,
                'agent_response': answer,
                'response_length': len(answer),
            }
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            interaction_count += 1
            print(f"[Logged to {LOG_FILE}]")
        
        except Exception as e:
            print(f"\n⚠ Error: {e}")
            print("Check your API key and internet connection")
            # Remove failed message from history
            conversation_history.pop()

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 56)
    print("  LOADING MISSION DOCUMENTATION...")
    print("=" * 56 + "\n")
    
    docs = load_documents()
    total_chars = sum(len(c) for c in docs.values())
    print(f"\n✓ Loaded {len(docs)} documents ({total_chars:,} total characters)")
    
    client, system_prompt = create_agent(docs)
    run_agent(client, system_prompt)