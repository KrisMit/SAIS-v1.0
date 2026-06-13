"""
INVISIBLE THREADS — Local LLM Experiment
Expedition Olympus, AATC, May 2026
Principal Investigator: Kristina Mitrovic

V5: Displays detailed crew metrics (NASA-TLX, PANAS, Env) upon login.
"""

import subprocess
import json
import os
import sys
import re

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL = "phi3:mini"
SOP_FILES = ["habitat_sops.txt", "habitat_manual.txt", "habitat_egress.txt"]
DATA_FILE = "expedition_olympus_data.json"

HIGH_LOAD_THRESHOLD = 70
MED_LOAD_THRESHOLD  = 40

# ─────────────────────────────────────────────────────────────
# DISPLAY CREW METRICS
# ─────────────────────────────────────────────────────────────
def display_crew_summary(data):
    """
    Prints a clean, formatted dashboard of the crew's current state.
    """
    if not data:
        return

    tlx = data.get('tlx', {})
    env = data.get('env', {})
    
    print("\n" + "─"*56)
    print(f" 📊 CREW STATUS DASHBOARD: {data.get('crew')} (DAY {data.get('day')})")
    print("─"*56)
    
    # NASA-TLX Section
    print(f" [NASA-TLX] Total Load: {data.get('tlx_total')}/100")
    print(f"   • Mental: {tlx.get('mental'):<3}  • Physical: {tlx.get('physical'):<3}  • Temporal: {tlx.get('temporal')}")
    print(f"   • Effort: {tlx.get('effort'):<3}  • Performance: {tlx.get('performance'):<3}  • Frustration: {tlx.get('frustration')}")
    
    # PANAS Section
    print(f"\n [PSYCH] PANAS Balance: {data.get('panas_balance'):+}")
    print(f"   • Positive Affect: {data.get('panas_pos')}  • Negative Affect: {data.get('panas_neg')}")
    
    # Environmental/Health Section
    print(f"\n [ENV/HEALTH]")
    print(f"   • Sleep Quality: {env.get('e1')}/10")
    print(f"   • Thermal Comfort: {env.get('e2')}")
    print(f"   • Habitat Suitability: {env.get('e6')}")
    print(f"   • Health Notes: {env.get('e8', 'None')}")
    print("─"*56)

# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
def load_crew_data(day, crew_id):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in data:
            if str(entry.get('day')) == str(day) and entry.get('crew') == crew_id:
                return entry
        return None
    except Exception as e:
        print(f"⚠ Data error: {e}")
        return None

def load_sops():
    content = ""
    print("📂 Loading SOP documents...")
    for file_path in SOP_FILES:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content += f"\n--- {file_path} ---\n" + f.read() + "\n"
            print(f"  ✓ {file_path}")
        except FileNotFoundError:
            pass
    return content

# ─────────────────────────────────────────────────────────────
# LLM LOGIC
# ─────────────────────────────────────────────────────────────
def get_relevant_context(question, full_content, max_chars=4000):
    paragraphs = full_content.split('\n\n')
    keywords = re.findall(r'\w{4,}', question.lower())
    if not keywords: return full_content[:max_chars]
    
    scored = []
    for p in paragraphs:
        score = sum(2 if w in p.lower() else 0 for w in keywords)
        if score > 0: scored.append((score, p))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    context = ""
    for _, p in scored:
        if len(context) + len(p) < max_chars: context += p + "\n\n"
    return context if context else full_content[:max_chars]

def ask_llm(prompt):
    try:
        print("⏳ Assistant is thinking...")
        result = subprocess.run(
            ['ollama', 'run', MODEL],
            input=prompt, capture_output=True, text=True, encoding='utf-8'
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# ─────────────────────────────────────────────────────────────
# MAIN SESSION
# ─────────────────────────────────────────────────────────────
def run_session():
    print("\n" + "="*56)
    print("  INVISIBLE THREADS — EXPEDITION OLYMPUS V5")
    print("="*56)

    full_sop = load_sops()
    
    day = input("\nMission day (1-8): ").strip() or "6"
    crew_id = input("Crew ID (e.g. EXP106CDR): ").strip() or "EXP106CDR"
    
    crew_data = load_crew_data(day, crew_id)
    
    if crew_data:
        display_crew_summary(crew_data)
    else:
        print(f"⚠ No data found for {crew_id} on Day {day}.")

    print(f"\nAssistant active. Type 'exit' to quit.")
    
    while True:
        question = input("\nYOUR QUESTION: ").strip()
        if not question: continue
        if question.lower() in ['exit', 'quit']: break
        
        context = get_relevant_context(question, full_sop)
        
        # Build prompt with crew context
        load = crew_data.get('tlx_total', 50) if crew_data else 50
        mode = "HIGH LOAD" if load >= HIGH_LOAD_THRESHOLD else "MODERATE" if load >= MED_LOAD_THRESHOLD else "NORMAL"
        
        prompt = f"""You are a Mars Assistant. Answer based ONLY on SOPs.
CREW STATUS: {crew_data if crew_data else 'Unknown'}
MODE: {mode}

SOP CONTEXT:
{context}

QUESTION: {question}
RESPONSE:"""
        
        response = ask_llm(prompt)
        print(f"\nASSISTANT ({mode}):\n{'-'*40}\n{response}\n{'-'*40}")

if __name__ == '__main__':
    run_session()
