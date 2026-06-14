"""
Local LLM Experiment
Expedition Olympus, AATC, May 2026
Commander: Kristina Mitrovic

Features:
- Robust CSV/JSON crew data loading with debug mode
- Detailed crew metrics dashboard (NASA-TLX, PANAS, Env)
- Curated dark humor library for crew morale
- SOP-based question answering via Ollama
"""

import subprocess
import json
import os
import sys
import re
import random
import csv
import glob

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL = "phi3:mini"
SOP_FILES = ["habitat_sops.txt", "habitat_manual.txt", "habitat_egress.txt"]

# Data sources (supports both JSON and CSV)
DATA_FILE = "expedition_olympus_data.json"

# Auto-detect CSV file (flexible naming)
def find_csv_file():
    """Auto-detect CSV file with flexible naming patterns."""
    patterns = [
        "expedition_olympus_crew_data.csv",
        "*crew_data*.csv",
        "*olympus*.csv",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return "expedition_olympus_crew_data.csv"  # fallback

CSV_DATA_FILE = find_csv_file()

HIGH_LOAD_THRESHOLD = 70
MED_LOAD_THRESHOLD  = 40

# Curated "Black Box" Humor Library for crew morale
DARK_HUMOR_JOKES = [
    "Mission Control says we're 'ahead of schedule.' That's great news—we'll starve three weeks early.",
    "The Hab's life support system is 99% reliable. That's oddly specific. I wonder what the 1% is.",
    "I love working in an enclosed environment with the same 11 people. It's like a group chat, but you can't leave, and there's literal poison outside.",
    "The good news: the dust storm passed. The bad news: the rover's now a submarine. In regolith. Which is worse, honestly.",
    "NASA says we're building 'humanity's future on Mars.' Spoiler: the future has a lot of duct tape and existential dread.",
    "My crewmate asked if we could have a private moment. I said, 'Sure, go stand in the corner where we can't quite hear you through the walls.'",
    "You know what's wild? This oxygen bottle is literally keeping me alive, and I'm angry at it. That's the kind of relationship energy we're working with.",
    "The commander asked if morale was low. I said, 'Define low.' She pointed out the airlock. Funny how perspective changes when you're trapped.",
    "We have a betting pool on who gets brought home first. I'm optimistic about my odds. That's probably a red flag.",
    "Day 47: We've started naming equipment. The spare oxygen tank is now 'Barry.' He's our favorite crew member. This is fine.",
    "The recycled water tastes like previous recycled water. It's water with a history. Water with regrets.",
    "Mission Control just asked if we're 'managing expectations.' Yes. My expectation is that we'll all be very thin by the time we leave.",
    "I told the team we're in this together. Nobody laughed. That's because we literally cannot leave each other.",
    "The AI keeps saying 'All systems nominal.' Buddy, I'm eating irradiated spaghetti in a metal bubble 140 million miles from pizza. Nothing is nominal."
]

# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────
def safe_int(val, default='—'):
    """Safely convert value to int, return default if fails."""
    try:
        if val == '' or val is None:
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

def get_available_crews(day=None):
    """Discover all crew IDs in both CSV and JSON files."""
    crews = set()
    
    # From CSV
    if os.path.exists(CSV_DATA_FILE):
        try:
            with open(CSV_DATA_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if day is None or str(row.get('day')) == str(day):
                        if row.get('crew'):
                            crews.add(row.get('crew'))
        except Exception: pass
    
    # From JSON
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for entry in data:
                    if day is None or str(entry.get('day')) == str(day):
                        if entry.get('crew'):
                            crews.add(entry.get('crew'))
        except Exception: pass
    
    return sorted(list(crews))

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
    source = data.get('_source', 'Unknown')
    
    print("\n" + "─"*56)
    print(f"CREW STATUS DASHBOARD: {data.get('crew')} (DAY {data.get('day')}) [{source}]")
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
    print(f"   • Crew Dynamic: {env.get('e2')}")
    print(f"   • Water Adequate: {env.get('e6')}")
    print(f"   • Health Notes: {env.get('e8', 'None')}")
    
    # Journal & Challenge Section (from CSV)
    if data.get('journal') or data.get('challenge'):
        print(f"\n [MISSION LOG]")
        if data.get('challenge'):
            print(f"   Challenge: {data.get('challenge')[:80]}")
        if data.get('positive_moment'):
            print(f"   Highlight: {data.get('positive_moment')[:80]}")
    
    print("─"*56)

# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
def load_crew_data(day, crew_id, debug=False):
    """Load crew data from CSV (preferred) or JSON with source tracking."""
    
    # Try CSV first
    if os.path.exists(CSV_DATA_FILE):
        try:
            if debug: print(f"Searching CSV: {CSV_DATA_FILE}")
            with open(CSV_DATA_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if str(row.get('day')) == str(day) and row.get('crew') == crew_id:
                        if debug: print(f"  ✓ Found in CSV!")
                        # Convert CSV row to expected dictionary format
                        data = {
                            'crew': row.get('crew'),
                            'day': int(row.get('day', 0)),
                            'tlx_total': safe_int(row.get('tlx_total', 50)),
                            'tlx': {
                                'mental': safe_int(row.get('tlx_mental')),
                                'physical': safe_int(row.get('tlx_physical')),
                                'temporal': safe_int(row.get('tlx_temporal')),
                                'effort': safe_int(row.get('tlx_effort')),
                                'performance': safe_int(row.get('tlx_performance')),
                                'frustration': safe_int(row.get('tlx_frustration')),
                            },
                            'panas_balance': safe_int(row.get('panas_balance')),
                            'panas_pos': safe_int(row.get('panas_positive_total')),
                            'panas_neg': safe_int(row.get('panas_negative_total')),
                            'env': {
                                'e1': safe_int(row.get('sleep_quality')),
                                'e2': row.get('crew_dynamic', 'Unknown'),
                                'e6': row.get('water_adequate', 'Unknown'),
                                'e8': row.get('symptoms', 'None'),
                            },
                            'journal': row.get('journal_text', ''),
                            'challenge': row.get('challenge', ''),
                            'positive_moment': row.get('positive_moment', ''),
                            '_source': 'CSV',
                        }
                        return data
        except Exception as e:
            print(f"⚠ CSV parse error: {e}")
            if debug: print(f"Debug: {type(e).__name__}")
    else:
        if debug: print(f"  ⚠ CSV file not found: {CSV_DATA_FILE}")
    
    # Fallback to JSON
    if os.path.exists(DATA_FILE):
        try:
            if debug: print(f"Searching JSON: {DATA_FILE}")
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in data:
                if str(entry.get('day')) == str(day) and entry.get('crew') == crew_id:
                    if debug: print(f"  ✓ Found in JSON!")
                    # Ensure JSON format is normalized
                    entry['_source'] = 'JSON'
                    return entry
            if debug: print(f"  ⚠ Crew {crew_id} not found on day {day} in JSON")
        except Exception as e:
            print(f"⚠ JSON parse error: {e}")
            if debug: print(f"Debug: {type(e).__name__}")
    else:
        if debug: print(f"  ⚠ JSON file not found: {DATA_FILE}")
    
    return None

def load_sops():
    """Load all SOP documents."""
    content = ""
    print(" Loading SOP documents...")
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
    """Extract relevant SOP context based on question."""
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
    """Query the local LLM via Ollama."""
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
    print("  INVISIBLE THREADS — EXPEDITION OLYMPUS COMPLETE")
    print("="*56)

    full_sop = load_sops()
    
    # Show available crews
    day = input("\nMission day (1-8): ").strip() or "6"
    available = get_available_crews(day)
    if available:
        print(f" Available crew IDs for Day {day}: {', '.join(available)}")
    else:
        print(f"⚠ No crews found for Day {day}")
        print(f"   Looking in: {CSV_DATA_FILE}, {DATA_FILE}")
    
    crew_id = input("Crew ID (e.g. EXP106CDR): ").strip() or "EXP106CDR"
    
    print(f"\n Loading crew data...")
    crew_data = load_crew_data(day, crew_id, debug=True)
    
    if crew_data:
        display_crew_summary(crew_data)
    else:
        print(f"\n❌ No data found for {crew_id} on Day {day}.")
        print(f"\n Expected file locations:")
        print(f"   CSV:  {os.path.abspath(CSV_DATA_FILE)}")
        print(f"   JSON: {os.path.abspath(DATA_FILE)}")
        print(f"\n All available crews: {', '.join(get_available_crews()) or 'None found'}")

    print(f"\nAssistant active. Type 'exit' to quit.")
   # print(f"Hint: Try 'dark humor' for morale boost!\n")
    
    while True:
        question = input("YOUR QUESTION: ").strip()
        if not question: continue
        if question.lower() in ['exit', 'quit']: break
        
        # Check for dark humor override
        if "dark humor" in question.lower():
            response = random.choice(DARK_HUMOR_JOKES)
            mode = "BLACK BOX HUMOR"
            print(f"\nASSISTANT ({mode}):\n{'-'*40}\n{response}\n{'-'*40}\n")
        else:
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
            print(f"\nASSISTANT ({mode}):\n{'-'*40}\n{response}\n{'-'*40}\n")

if __name__ == '__main__':
    run_session()
