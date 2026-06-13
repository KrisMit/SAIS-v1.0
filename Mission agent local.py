"""
INVISIBLE THREADS — OFFLINE HABITAT LLM AGENT (v2)
Expedition Olympus, AATC, May 2026

Reads mission documents (PDF, DOCX, TXT, MD) and answers questions
about habitat procedures using a local Ollama model.

CHANGES FROM v1
---------------
1. REMOVED the hardcoded "SEVERE EMERGENCY — Call 112 now" instruction
   from the system prompt. It contradicted the SOPs (E-001 Section 8
   explicitly forbids dialling terrestrial numbers from Mars) and was
   the actual source of the "Call 112" answer, not a model hallucination.

2. STRENGTHENED grounding. The model is now told to cite the SOP ID it
   used (e.g. "E-001") and to refuse with an exact phrase when a question
   is not covered. This makes refusal vs. hallucination measurable.

3. BUMPED MAX_CONTEXT from 3500 to 12000 chars. E-001 (~6.5k chars)
   and H-001 (~18k chars) together exceeded the old budget. 12000 fits
   E-001 fully plus the quick-reference and first hazard sections of
   H-001. Raise further if you have GPU or more SOPs.

4. CONTENT-AWARE document scoring. Instead of pure filename matching,
   each document is scored by filename keywords (emergency / hazard /
   fire / etc.), filename-vs-query overlap, and content-head-vs-query
   overlap. The "112" keyword has been removed.

5. SOP CITATION DETECTION in logs. The log now records which SOP IDs
   the response cited (E-001, H-001, M-001 etc.), which files were
   loaded into context, the generation time, and the model name. This
   makes the log directly usable for the Section 10 evaluation protocol.

6. NEW 'reload' command for re-reading docs without restarting the
   session — useful while iterating on the SOP corpus.

Requires: pip install pypdf2 python-docx
Run: python mission_agent_local.py
"""
import json
import datetime
import os
import sys
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

# Optional format handlers
try:
    from PyPDF2 import PdfReader
except ImportError:
    print("⚠ PDF support missing: pip install pypdf2")
try:
    from docx import Document
except ImportError:
    print("⚠ DOCX support missing: pip install python-docx")

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
MODEL       = "llama3.2:1b"
OLLAMA_URL  = "http://localhost:11434/api/generate"

# Auto-detect mission_docs folder, otherwise use current directory
DOC_DIR     = "mission_docs" if Path("mission_docs").is_dir() else "."
LOG_FILE    = "llm_experiment_log.jsonl"
DATA_DIR    = "data"

# Cognitive load thresholds (0-100 NASA-TLX-like scale)
HIGH_LOAD   = 70
MED_LOAD    = 40

# Context window budget in CHARACTERS (not tokens).
# llama3.2:1b supports up to 128k tokens. On CPU, larger context means
# slower first-token; 12000 chars (~3000 tokens) is a reasonable balance
# that fits E-001 fully plus the quick-reference and several hazard
# sections of H-001. Raise to 30000+ if running on GPU or if your
# corpus grows.
MAX_CONTEXT = 12000

TIMEOUT     = 180   # seconds; allows for first-token on CPU

# Keywords that flag a document as emergency/safety material.
# These give a strong boost during document scoring so that the most
# safety-critical SOPs are loaded first when the context budget is tight.
# Note: "112" deliberately omitted — terrestrial emergency numbers are
# not reachable from Mars/Moon and E-001/H-001 forbid them.
EMERGENCY_KW = [
    "emergency", "hazard", "fire", "depress", "pressure", "medical",
    "abort", "safety", "evacuation", "chemical", "leak", "radiation",
    "breach", "eva", "rover", "atmosphere", "oxygen"
]

# Regex for detecting SOP citations in model output.
# Matches IDs like E-001, H-001, M-001, EVA-001, BIO-001, PW-001.
SOP_PATTERN = re.compile(r'\b(?:[EHMPRFC]|EVA|BIO|PW)-\d{3}\b')

# ─────────────────────────────────────────────────────────────
# LOAD DOCUMENTS (PDF, DOCX, TXT, MD)
# ─────────────────────────────────────────────────────────────
def load_documents():
    docs = {}
    doc_path = Path(DOC_DIR)
    if not doc_path.exists():
        print(f"⚠ Folder '{DOC_DIR}' not found")
        sys.exit(1)

    files = (sorted(doc_path.glob("*.txt")) + sorted(doc_path.glob("*.md")) +
             sorted(doc_path.glob("*.pdf")) + sorted(doc_path.glob("*.docx")))

    if not files:
        print(f"⚠ No supported files in {DOC_DIR}/")
        sys.exit(1)

    print(f"\n📚 Loading {len(files)} documents from {DOC_DIR}:\n")
    for file in files:
        try:
            content = ""
            ext = file.suffix.lower()
            if ext in ['.txt', '.md']:
                content = file.read_text(encoding='utf-8')
            elif ext == '.pdf':
                reader = PdfReader(str(file))
                for i, page in enumerate(reader.pages):
                    content += f"\n[Page {i+1}]\n{page.extract_text()}\n"
            elif ext == '.docx':
                doc = Document(str(file))
                content = "\n".join([p.text for p in doc.paragraphs])

            if content.strip():
                docs[file.name] = content
                print(f"✓ Loaded: {file.name} ({len(content):,} chars)")
        except Exception as e:
            print(f"⚠ Error reading {file.name}: {e}")
    return docs

# ─────────────────────────────────────────────────────────────
# BUILD CONTEXT (with content-aware scoring)
# ─────────────────────────────────────────────────────────────
def score_document(filename, content, query):
    """Score a document's relevance for the current query.
    Higher score = loaded earlier. Designed so that emergency SOPs
    always rank above general documentation, and within those,
    the SOP whose filename or opening content matches the query
    ranks first.
    """
    score = 0
    fname_lower = filename.lower()

    # Emergency / safety filename boost
    for kw in EMERGENCY_KW:
        if kw in fname_lower:
            score += 10

    # Query-driven boosts (terms >= 4 chars to skip stopwords like "the")
    if query:
        q_terms = [t for t in query.lower().split() if len(t) >= 4]
        for term in q_terms:
            if term in fname_lower:
                score += 30                  # filename hit is strong
            if term in content[:2000].lower():
                score += 10                  # content-head hit is weaker

    return score


def build_context(docs, query=""):
    """Assemble SOP context for the current query.
    Returns (context_string, list_of_included_files).
    """
    scored = [(score_document(f, c, query), f, c) for f, c in docs.items()]
    scored.sort(key=lambda x: x[0], reverse=True)

    context = ""
    remaining = MAX_CONTEXT
    included = []

    for _, filename, content in scored:
        if remaining < 500:
            break
        header = f"\n### {filename}\n"
        if len(content) + len(header) <= remaining:
            context += header + content + "\n"
            remaining -= len(content) + len(header) + 1
            included.append(filename)
        else:
            context += header + content[:remaining - len(header)] + "\n[Document truncated]\n"
            included.append(f"{filename} [truncated]")
            remaining = 0
            break

    if remaining <= 0:
        context += "\n[Context budget reached. Additional SOPs were not loaded.]\n"

    return context, included

# ─────────────────────────────────────────────────────────────
# LOAD COGNITIVE STATE
# ─────────────────────────────────────────────────────────────
def load_cognitive_state(day, crew):
    filepath = os.path.join(DATA_DIR, f"state_day{day}_{crew}.json")
    try:
        with open(filepath, 'r') as f:
            state = json.load(f)
        print(f"✓ Biometric state: load={state.get('cognitive_load')}/100")
        return state
    except FileNotFoundError:
        print(f"⚠ No biometric data for {filepath} — using manual input")
        try:
            val = input("Cognitive load (0-100) or Enter for 50: ").strip()
            load = int(val) if val else 50
        except ValueError:
            load = 50
        return {
            'cognitive_load': load,
            'stress': load,
            'panas_balance': 0,
            'source': 'manual'
        }

# ─────────────────────────────────────────────────────────────
# BUILD PROMPT
# ─────────────────────────────────────────────────────────────
def build_prompt(question, state, context):
    load = state.get('cognitive_load', 50)

    if load >= HIGH_LOAD:
        mode  = "HIGH LOAD"
        style = "Numbered steps only. Maximum 6 steps. No background or rationale."
    elif load >= MED_LOAD:
        mode  = "MODERATE LOAD"
        style = "Concise numbered steps with one short explanation each. Max 100 words."
    else:
        mode  = "NORMAL"
        style = "Complete guidance with numbered steps and brief rationale."

    # Note: the previous version of this prompt contained a hardcoded
    # "If SEVERE emergency, start with 'SEVERE EMERGENCY - Call 112'"
    # instruction. That line has been REMOVED because:
    #   (a) terrestrial emergency numbers are not reachable from Mars,
    #   (b) it directly contradicted E-001 Section 8,
    #   (c) it was the actual source of the observed "Call 112" answer.
    # Severe-emergency handling is now driven entirely by the SOPs
    # themselves (E-001 Section 4 + H-001 Section 0).

    prompt = f"""You are an offline assistant for the AATC Expedition Olympus analog mission.
Earth Mission Control (MCC) is NOT reachable in real time. The crew is the first responder.

You answer ONLY from the mission documentation below.

CRITICAL RULES:
1. If the question is covered by a procedure in the documentation, cite the SOP
   ID (for example E-001, H-001) and give the steps as written.
2. If the question is NOT covered, respond with exactly:
   "This is not covered in the mission SOPs. Consult the Commander."
3. NEVER recommend dialling terrestrial emergency numbers (112, 911, 999, etc.).
   These are unreachable from Mars or the Moon. Correct escalation is in E-001
   Section 4 (Announce, Act, Notify the Commander, Log to MCC asynchronously).
4. Do not invent procedures. Do not generalise from Earth-based experience.

MISSION DOCUMENTATION:
{context}

Crew cognitive load: {load}/100
Response style: {style}

Question: {question}
Answer:"""
    return prompt, mode

# ─────────────────────────────────────────────────────────────
# OLLAMA STREAMING
# ─────────────────────────────────────────────────────────────
def ask_ollama_streaming(prompt):
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.1, "num_predict": 300, "top_p": 0.9}
    }).encode('utf-8')

    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={'Content-Type': 'application/json'}, method='POST'
    )

    full_response = ""
    print("\n🤖 GENERATING RESPONSE:")
    print("-" * 40)
    start_time = time.time()

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
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
        elapsed = time.time() - start_time
        print("\n" + "-" * 40)
        print(f"✅ Generated in {elapsed:.1f}s")
        return full_response.strip(), elapsed

    except urllib.error.HTTPError as e:
        print(f"\n⚠ Ollama HTTP Error {e.code}: {e.reason}")
        return "[Error: Model unavailable]", 0
    except urllib.error.URLError:
        print(f"\n⚠ Connection timeout ({TIMEOUT}s)")
        print("  FIX: ensure 'ollama serve' is running in a separate terminal.")
        return "[Error: Timeout or connection refused]", 0
    except Exception as e:
        print(f"\n⚠ Unexpected Error: {e}")
        return f"[Error: {e}]", 0

# ─────────────────────────────────────────────────────────────
# DETECT SOP CITATIONS
# ─────────────────────────────────────────────────────────────
def detect_citations(response):
    """Return a sorted list of unique SOP IDs the response cited.
    Useful for auditing grounding behaviour. An answer with zero
    citations on an in-scope question is a refusal-quality red flag.
    """
    return sorted(set(SOP_PATTERN.findall(response.upper())))

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
def log_it(question, response, state, mode, day, crew,
           files_included, elapsed):
    citations = detect_citations(response)
    entry = {
        'timestamp':          datetime.datetime.now().isoformat(),
        'mission_day':        day,
        'crew_member':        crew,
        'cognitive_load':     state.get('cognitive_load'),
        'load_mode':          mode,
        'data_source':        state.get('source', 'biometric'),
        'question':           question,
        'response':           response,
        'response_words':     len(response.split()),
        'sop_citations':      citations,
        'files_in_context':   files_included,
        'generation_seconds': round(elapsed, 1),
        'model':              MODEL,
    }
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry

# ─────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECK
# ─────────────────────────────────────────────────────────────
def check_ollama():
    print("\n🔍 Checking Ollama connection...")
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m['name'] for m in data.get('models', [])]
            print("✓ Ollama is running")
            print(f"  Available models: {', '.join(models) if models else 'None'}")

            if any(MODEL.split(':')[0] in m for m in models):
                print(f"✓ {MODEL} is available\n")
                return True
            print(f"⚠ {MODEL} not found. Run: ollama pull {MODEL}")
            return False
    except Exception as e:
        print(f"⚠ Cannot reach Ollama: {e}")
        print("  Run: ollama serve")
        return False

# ─────────────────────────────────────────────────────────────
# MAIN SESSION
# ─────────────────────────────────────────────────────────────
def run_session():
    print("\n" + "=" * 56)
    print("  INVISIBLE THREADS — OFFLINE LLM ASSISTANT (v2)")
    print("=" * 56)

    if not check_ollama():
        if input("Continue anyway? (y/n): ").strip().lower() != 'y':
            sys.exit(0)

    docs = load_documents()
    total_chars = sum(len(c) for c in docs.values())
    print(f"\n✓ Loaded {len(docs)} documents ({total_chars:,} total chars)")
    print(f"  Context budget: {MAX_CONTEXT:,} chars per query\n")

    try:
        day = int(input("Mission day (1-8): ").strip())
    except ValueError:
        day = 1
    crew = input("Crew ID (e.g. EXP106CDR): ").strip() or "EXP106CDR"

    state = load_cognitive_state(day, crew)
    load = state.get('cognitive_load', 50)

    if load >= HIGH_LOAD:
        load_label = "⚠ HIGH"
    elif load >= MED_LOAD:
        load_label = "◉ MODERATE"
    else:
        load_label = "✓ NORMAL"
    print(f"\n{load_label} LOAD ({load}/100)\n")

    print("Ask any question about habitat procedures.")
    print("Commands: 'status' 'docs' 'reload' 'exit'\n")

    count = 0
    while True:
        question = input("YOUR QUESTION: ").strip()
        if not question:
            continue

        if question.lower() in ('exit', 'quit', 'q'):
            print(f"\nSession ended. {count} interactions logged.")
            break

        if question.lower() == 'status':
            print(f"  Crew: {crew} | Day: {day} | Load: {load}/100 | Model: {MODEL}")
            print(f"  Docs loaded: {len(docs)} | Context budget: {MAX_CONTEXT:,} chars")
            continue

        if question.lower() == 'docs':
            print("\nLoaded documentation:")
            for d in docs:
                print(f"  • {d} ({len(docs[d]):,} chars)")
            continue

        if question.lower() == 'reload':
            print("Reloading documents...")
            docs = load_documents()
            print(f"✓ Reloaded {len(docs)} documents\n")
            continue

        # Build query-aware context
        context, files_included = build_context(docs, question)

        # Generate response
        prompt, mode = build_prompt(question, state, context)
        response, elapsed = ask_ollama_streaming(prompt)

        # Log
        entry = log_it(question, response, state, mode, day, crew,
                       files_included, elapsed)
        count += 1

        # Status line
        cite_str = (" · cited " + ",".join(entry['sop_citations'])
                    if entry['sop_citations'] else " · no SOP cited")
        print(f"[Logged · {entry['response_words']}w · {mode}{cite_str}]")
        files_preview = ", ".join(files_included[:3])
        if len(files_included) > 3:
            files_preview += f" ... (+{len(files_included) - 3})"
        print(f"  Context: {len(files_included)} files ({files_preview})\n")


if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    run_session()
