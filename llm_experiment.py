"""
INVISIBLE THREADS — Local LLM Experiment
Expedition Olympus, AATC, May 2026
Principal Investigator: Kristina Mitrovic

This script runs a local offline LLM (Phi-3 Mini via Ollama)
that provides SOP guidance to crew members during communication
blackout periods. Response complexity adapts automatically to
the crew member's current cognitive load from biometric data.
"""

import subprocess
import json
import datetime
import os
import sys

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL = "phi3:mini"                     # Local model via Ollama
SOP_FILE = "habitat_sops.txt"          # Your SOP document
LOG_FILE = "llm_experiment_log.jsonl"  # Research log
DATA_DIR = "data"                       # Biometric state files

# Cognitive load thresholds
HIGH_LOAD_THRESHOLD = 70   # Above this = simplified responses
MED_LOAD_THRESHOLD  = 40   # Above this = moderate responses

# ─────────────────────────────────────────────────────────────
# LOAD SOPs
# ─────────────────────────────────────────────────────────────
def load_sops():
    try:
        with open(SOP_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✓ SOPs loaded ({len(content)} characters)")
        return content
    except FileNotFoundError:
        print(f"⚠ SOP file not found: {SOP_FILE}")
        print("  Place habitat_sops.txt in the same folder as this script.")
        sys.exit(1)

# ─────────────────────────────────────────────────────────────
# LOAD COGNITIVE STATE
# Reads from biometric pipeline output
# Falls back to manual input if no data available yet
# ─────────────────────────────────────────────────────────────
def load_cognitive_state(day, crew_member):
    filepath = os.path.join(DATA_DIR, f"state_day{day}_{crew_member}.json")
    try:
        with open(filepath, 'r') as f:
            state = json.load(f)
        print(f"✓ Biometric state loaded for {crew_member} Day {day}")
        print(f"  Cognitive load : {state.get('cognitive_load', 'N/A')}/100")
        print(f"  Stress index   : {state.get('stress', 'N/A')}/100")
        print(f"  PANAS balance  : {state.get('panas_balance', 'N/A')}")
        return state
    except FileNotFoundError:
        print(f"⚠ No biometric data found for {crew_member} Day {day}")
        print(f"  Expected file: {filepath}")
        print()
        # Manual fallback — crew member self-reports
        try:
            manual = int(input(
                "Enter current cognitive load manually (0-100, "
                "or press Enter to use default 50): "
            ).strip() or "50")
            return {
                'cognitive_load': manual,
                'stress': manual,
                'panas_balance': 0,
                'source': 'manual_input'
            }
        except ValueError:
            return {
                'cognitive_load': 50,
                'stress': 50,
                'panas_balance': 0,
                'source': 'default'
            }

# ─────────────────────────────────────────────────────────────
# BUILD PROMPT
# Adapts complexity instruction based on cognitive load
# ─────────────────────────────────────────────────────────────
def build_prompt(question, cognitive_state, sop_content):
    load = cognitive_state.get('cognitive_load', 50)

    if load >= HIGH_LOAD_THRESHOLD:
        mode = "HIGH COGNITIVE LOAD"
        instruction = (
            "The crew member is under HIGH cognitive load. "
            "Give ONLY numbered steps. Maximum 6 steps. "
            "No explanations, no background, no extra text. "
            "Short imperative sentences only. "
            "Example format: '1. Do X. 2. Do Y. 3. Report to MCC.'"
        )
    elif load >= MED_LOAD_THRESHOLD:
        mode = "MODERATE COGNITIVE LOAD"
        instruction = (
            "The crew member is under moderate cognitive load. "
            "Be clear and concise. Use numbered steps. "
            "Include one short explanation per step if critical. "
            "Keep total response under 150 words."
        )
    else:
        mode = "NORMAL COGNITIVE LOAD"
        instruction = (
            "The crew member is calm and alert. "
            "Provide complete, clear guidance. "
            "Include context and reasoning where helpful. "
            "Use numbered steps with brief explanations."
        )

    prompt = f"""You are an autonomous habitat assistant for an analog Mars mission at AATC.
You are operating during a communication blackout — MCC is unreachable.
Your role is to guide crew members through standard operating procedures.

CURRENT CREW STATUS:
- Cognitive load: {load}/100 ({mode})
- Stress level: {cognitive_state.get('stress', 'unknown')}/100
- Response mode: {instruction}

STANDARD OPERATING PROCEDURES:
{sop_content}

CREW QUESTION:
{question}

INSTRUCTIONS:
- Answer ONLY using the SOPs provided above
- If the answer is not in the SOPs, say: "This is not covered in the SOPs. Contact MCC when communication is restored."
- Never invent procedures not in the document
- Adjust your response complexity according to the crew status above
- If this is a severe emergency (fire, injury, loss of pressure), immediately state: "THIS IS A SEVERE EMERGENCY — Call 112 now" as your first line

RESPONSE:"""

    return prompt, mode

# ─────────────────────────────────────────────────────────────
# CALL LOCAL LLM
# ─────────────────────────────────────────────────────────────
def ask_llm(prompt):
    try:
        print("\n⏳ Processing... (this may take 10-30 seconds)")
        result = subprocess.run(
            ['ollama', 'run', MODEL, prompt],
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8'
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: Response timed out. Try a simpler question."
    except FileNotFoundError:
        return (
            "Error: Ollama not found. "
            "Ensure Ollama is installed and running. "
            "Start it with: ollama serve"
        )
    except Exception as e:
        return f"Unexpected error: {str(e)}"

# ─────────────────────────────────────────────────────────────
# LOG INTERACTION
# Records everything for post-mission analysis
# ─────────────────────────────────────────────────────────────
def log_interaction(question, response, cognitive_state, mode, day, crew):
    entry = {
        'timestamp'       : datetime.datetime.now().isoformat(),
        'mission_day'     : day,
        'crew_member'     : crew,
        'cognitive_load'  : cognitive_state.get('cognitive_load'),
        'stress'          : cognitive_state.get('stress'),
        'panas_balance'   : cognitive_state.get('panas_balance'),
        'load_mode'       : mode,
        'data_source'     : cognitive_state.get('source', 'biometric_file'),
        'question'        : question,
        'response'        : response,
        'response_words'  : len(response.split()),
        'response_lines'  : len(response.strip().split('\n')),
    }
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry

# ─────────────────────────────────────────────────────────────
# CHECK OLLAMA IS RUNNING
# ─────────────────────────────────────────────────────────────
def check_ollama():
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True, text=True, timeout=10
        )
        if MODEL.replace(':','') in result.stdout.replace(':',''):
            print(f"✓ Ollama running · Model {MODEL} available")
            return True
        else:
            print(f"⚠ Model {MODEL} not found.")
            print(f"  Run: ollama pull {MODEL}")
            return False
    except Exception:
        print("⚠ Ollama not running. Start with: ollama serve")
        return False

# ─────────────────────────────────────────────────────────────
# MAIN SESSION
# ─────────────────────────────────────────────────────────────
def run_session():
    print()
    print("=" * 56)
    print("  INVISIBLE THREADS — OFFLINE LLM ASSISTANT")
    print("  Expedition Olympus · AATC · Offline Mode")
    print("=" * 56)

    # Check Ollama
    if not check_ollama():
        input("\nPress Enter to continue anyway (responses will fail)...")

    # Load SOPs
    sop_content = load_sops()

    # Get mission day and crew
    print()
    try:
        day = int(input("Mission day (1-8): ").strip())
    except ValueError:
        day = 1
    crew = input("Crew ID (e.g. CM-01): ").strip() or "CM-01"

    # Load cognitive state
    print()
    cognitive_state = load_cognitive_state(day, crew)

    # Show current mode
    load = cognitive_state.get('cognitive_load', 50)
    print()
    if load >= HIGH_LOAD_THRESHOLD:
        print(f"⚠ HIGH LOAD DETECTED ({load}/100)")
        print("  Responses will be simplified to numbered steps only.")
    elif load >= MED_LOAD_THRESHOLD:
        print(f"◉ MODERATE LOAD ({load}/100)")
        print("  Responses will be concise with brief explanations.")
    else:
        print(f"✓ NORMAL LOAD ({load}/100)")
        print("  Full responses with context available.")

    print()
    print("Ask any question about habitat procedures.")
    print("Type 'status' to see current cognitive state.")
    print("Type 'exit' to end session.")
    print("-" * 56)

    session_count = 0

    while True:
        print()
        question = input("YOUR QUESTION: ").strip()

        if not question:
            continue

        if question.lower() in ['exit', 'quit', 'q']:
            print(f"\nSession ended. {session_count} interaction(s) logged.")
            break

        if question.lower() == 'status':
            print(f"\n  Crew     : {crew}")
            print(f"  Day      : {day}")
            print(f"  Load     : {load}/100")
            print(f"  Stress   : {cognitive_state.get('stress')}/100")
            print(f"  Source   : {cognitive_state.get('source', 'biometric')}")
            continue

        # Build prompt and ask LLM
        prompt, mode = build_prompt(question, cognitive_state, sop_content)
        response = ask_llm(prompt)

        # Display response
        print()
        print("ASSISTANT:")
        print("-" * 40)
        print(response)
        print("-" * 40)

        # Log interaction
        entry = log_interaction(
            question, response, cognitive_state, mode, day, crew
        )
        session_count += 1
        print(
            f"[Logged · {entry['response_words']} words · "
            f"Load mode: {mode}]"
        )

# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    run_session()