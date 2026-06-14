"""
INVISIBLE THREADS — Local LLM Experiment
Expedition Olympus, AATC, May 2026
Principal Investigator: Kristina Mitrovic

V8: Includes a curated "Black Box" library of space-themed dark humor.
"""

import subprocess
import json
import os
import random
import re

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL = "phi3:mini"
SOP_FILES = ["habitat_sops.txt", "habitat_manual.txt", "habitat_egress.txt"]
DATA_FILE = "expedition_olympus_data.json"

# Curated "Black Box" Humor Library
DARK_HUMOR_JOKES = [
    "The good news: The life support system is fixed. The bad news: It only supports the person who fixed it. Good luck.",
    "Why don't we tell secrets on Mars? Because the walls are thin, and the atmosphere is even thinner. Just like your chances of going home.",
    "In space, no one can hear you scream. But the mission recorder hears everything. Try to die quietly, it's for the data.",
    "What's the difference between a Mars explorer and a shooting star? One is a beautiful streak of light, and the other is just a very expensive funeral.",
    "My crewmate asked me to help him with his 'space suit' problem. I told him the airlock was the best place to find 'extra space'.",
    "I'm not saying the mission is failing, but I've started referring to the 'Hab' as the 'Crypt'.",
    "Oxygen is like money. You only realize how much you need it when you're completely out. And currently, you're bankrupt.",
    "Why did the astronaut's wife leave him? He said he needed 'space'. So she pushed him out the airlock. Problem solved.",
    "The AI says we have a 1% chance of survival. I like those odds. It means I only have to kill 99 of you to be the lucky one.",
    "Don't worry about the red light on the oxygen tank. It just means you'll be seeing the 'white light' very soon."
]

# ─────────────────────────────────────────────────────────────
# DISPLAY & DATA LOGIC
# ─────────────────────────────────────────────────────────────
def display_crew_summary(data):
    if not data: return
    tlx, env = data.get('tlx', {}), data.get('env', {})
    print("\n" + "─"*56 + f"\n 📊 STATUS: {data.get('crew')} (DAY {data.get('day')})\n" + "─"*56)
    print(f" [LOAD] Total: {data.get('tlx_total')}/100 | Mental: {tlx.get('mental')} | Frustration: {tlx.get('frustration')}")
    print(f" [PSYCH] PANAS: {data.get('panas_balance'):+} | [HEALTH] {env.get('e8', 'None')}\n" + "─"*56)

def load_crew_data(day, crew_id):
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for entry in data:
            if str(entry.get('day')) == str(day) and entry.get('crew') == crew_id: return entry
    except Exception: pass
    return None

def load_sops():
    content = ""
    for f_path in SOP_FILES:
        try:
            with open(f_path, 'r', encoding='utf-8') as f: content += f.read() + "\n"
        except FileNotFoundError: pass
    return content

# ─────────────────────────────────────────────────────────────
# LLM & SESSION
# ─────────────────────────────────────────────────────────────
def ask_llm(prompt):
    try:
        print("⏳ Processing...")
        result = subprocess.run(['ollama', 'run', MODEL], input=prompt, capture_output=True, text=True, encoding='utf-8')
        return result.stdout.strip()
    except Exception as e: return f"Error: {str(e)}"

def run_session():
    print("\n" + "="*56 + "\n  INVISIBLE THREADS — V8 (BLACK BOX HUMOR)\n" + "="*56)
    full_sop = load_sops()
    day = input("\nDay: ").strip() or "6"
    crew_id = input("Crew ID: ").strip() or "EXP106CDR"
    crew_data = load_crew_data(day, crew_id)
    if crew_data: display_crew_summary(crew_data)
    
    while True:
        question = input("\nYOUR QUESTION: ").strip()
        if question.lower() in ['exit', 'quit']: break
        
        # Check for dark humor keyword
        if "dark humor" in question.lower():
            response = random.choice(DARK_HUMOR_JOKES)
            mode = "BLACK BOX HUMOR"
        else:
            mode = "SOP MODE"
            prompt = f"You are a Mars Assistant. Answer based ONLY on SOPs. Question: {question}\nSOP Context: {full_sop[:2000]}"
            response = ask_llm(prompt)
            
        print(f"\nASSISTANT ({mode}):\n{'-'*40}\n{response}\n{'-'*40}")

if __name__ == '__main__':
    run_session()
