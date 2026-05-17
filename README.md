# SAIS v1.0 - Space AI System for Deep Space Exploration

Full implementations referenced in:
**Mitrovic, K. (2026). SAIS v1.0: A Hybrid Autonomous Decision Architecture 
for Deep Space Exploration. AATC Expedition Olympus Technical Report.**

## Repository Structure

```
sais-v1.0/
├── layers/
│   ├── space_ai_ststem(sais).py          # Fuzzy Safety Guardian
│   ├── space_ai_ststem(sais).py          # ML anomaly detection
│   ├── space_ai_ststem(sais).py          # Bayesian diagnostics
│   ├── space_ai_ststem(sais).py          # Decision synthesis
│   └── llm_experiment.py.py              # Document-grounded LLM
│   └── mission_agent_claude.py           #claude ai agent
│   └── mission_agent_local.py            #local AI agent
│
├── invisible_threads/
│   ├── pulse_reveal.js                 # rPPG algorithm (WebAR)
│   ├── invisible_threads.html          # Interactive art installation
│   └── mission_day_mapping.json
│
├── analysis/
│   ├── analysis.py                    # NASA-TLX analysis
│   ├── visualization.py               # Dashboard & plotting
│   
│
├── evaluation/
│   ├── pre_registered_protocol.md     # Section 9 evaluation spec
│   └── synthetic_dataset.csv
│
└── README.md (this file)
```
