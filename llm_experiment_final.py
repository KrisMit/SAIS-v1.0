"""
INVISIBLE THREADS — Local LLM Experiment
Expedition Olympus, AATC, May 2026
Principal Investigator: Kristina Mitrovic

FIXED VERSION: Handles multiple SOPs and large file sizes on Windows.
"""

import subprocess
import json
import datetime
import os
import sys

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL = "phi3:mini"
# We use a list here so the script can loop through them
SOP_FILES = ["habitat_sops.txt", "habitat_manual.txt", "habitat_egress.txt"]
LOG_FILE = "llm_experiment_log.jsonl"
DATA_DIR = "data"

HIGH_LOAD_THRESHOLD = 70
MED_LOAD_THRESHOLD  = 40

# ─────────────────────────────────────────────────────────────
# LOAD SOPs (FIXED: Loops through multiple files)
# ─────────────────────────────────────────────────────────────
def load_sops():
    combined_content = ""
    files_found = 0
    print("📂 Loading SOP documents...")
    
    for file_path in SOP_FILES:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                combined_content += f"\n\n--- DOCUMENT: {file_path} ---\n{content}"
            files_found += 1
            print(f"  ✓ Loaded: {file_path}")
        except FileNotFoundError:
            print(f"  ⚠ Warning: File not found: {file_path}")

    if files_found == 0:
        print("\n❌ Error: No SOP files found. Check your file names and folder.")
        sys.exit(1)
        
    print(f"✓ Total SOPs loaded ({len(combined_content)} characters)")
    return combined_content

# ─────────────────────────────────────────────────────────────
# LOAD COGNITIVE STATE
# ─────────────────────────────────────────────────────────────
def load_cognitive_state(day, crew_member):
    filepath = os.path.join(DATA_DIR, f"state_day{day}_{crew_member}.json")
    try:
        with open(filepath, 'r') as f:
            state = json.load(f)
        print(f"✓ Biometric state loaded for {crew_member}")
        state['source'] = 'biometric_file'
        return state
    except FileNotFoundError:
        print(f"⚠ No biometric data found for {crew_member}. Using manual entry.")
        try:
            manual = int(input("Enter cognitive load (0-100, default 50): ").strip() or "50")
            return {'cognitive_load': manual, 'stress': manual, 'panas_balance': 0, 'source': 'manual'}
        except ValueError:
            return {'cognitive_load': 50, 'stress': 50, 'panas_balance': 0, 'source': 'default'}

# ─────────────────────────────────────────────────────────────
# BUILD PROMPT
# ─────────────────────────────────────────────────────────────
def build_prompt(question, cognitive_state, sop_content):
    load = cognitive_state.get('cognitive_load', 50)
    
    if load >= HIGH_LOAD_THRESHOLD:
        mode, instruction = "HIGH LOAD", "ONLY numbered steps. Max 6 steps. No explanations."
    elif load >= MED_LOAD_THRESHOLD:
        mode, instruction = "MODERATE LOAD", "Concise numbered steps. Max 150 words."
    else:
        mode, instruction = "NORMAL LOAD", "Full guidance with context and reasoning."

    prompt = f"""You are a habitat assistant for an analog Mars mission. 
Answer based ONLY on the SOPs provided. 

CREW STATUS: Load {load}/100 ({mode})
INSTRUCTION: {instruction}

SOP DATA:
{sop_content}

QUESTION: {question}
RESPONSE:"""
    return prompt, mode

# ─────────────────────────────────────────────────────────────
# CALL LOCAL LLM (FIXED: Uses stdin to bypass Windows limits)
# ─────────────────────────────────────────────────────────────
def ask_llm(prompt):
    try:
        print("\n⏳ Processing... (Reading 60k+ characters of SOPs)")
        # We pass the prompt to 'input' so it doesn't break the command line limit
        result = subprocess.run(
            ['ollama', 'run', MODEL],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=180
        )
        if result.returncode != 0:
            return f"Ollama Error: {result.stderr}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: The SOPs are very large and the model timed out."
    except Exception as e:
        return f"System Error: {str(e)}"

# ─────────────────────────────────────────────────────────────
# MAIN SESSION
# ─────────────────────────────────────────────────────────────
def run_session():
    print("\n" + "="*56)
    print("  INVISIBLE THREADS — OFFLINE LLM ASSISTANT")
    print("  Expedition Olympus · AATC · Fixed V3")
    print("="*56)

    sop_content = load_sops()
    
    day = input("\nMission day (1-8): ").strip() or "1"
    crew = input("Crew ID (e.g. EXP106CDR): ").strip() or "CM-01"
    
    cognitive_state = load_cognitive_state(day, crew)
    load = cognitive_state.get('cognitive_load', 50)
    
    print(f"\nMode: {load}/100 detected. Type 'exit' to quit.")
    
    while True:
        question = input("\nYOUR QUESTION: ").strip()
        if not question: continue
        if question.lower() in ['exit', 'quit']: break
        
        prompt, mode = build_prompt(question, cognitive_state, sop_content)
        response = ask_llm(prompt)
        
        print(f"\nASSISTANT:\n{'-'*40}\n{response}\n{'-'*40}")

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    run_session()
