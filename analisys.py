import pandas as pd
import json

# Load all interactions
interactions = []
with open('llm_experiment_log.jsonl', 'r') as f:
    for line in f:
        interactions.append(json.loads(line))

df = pd.DataFrame(interactions)

# Key research questions:
# 1. Did response length decrease when cognitive load was high?
print(df.groupby(pd.cut(df['cognitive_load'], bins=[0,40,70,100], 
      labels=['Low','Medium','High']))['response_length'].mean())

# 2. Which days had most queries? (peak stress days)
print(df.groupby('day')['question'].count())

# 3. Correlation between load and query frequency
from scipy import stats
r, p = stats.pearsonr(df['cognitive_load'], df['response_length'])
print(f"Correlation load vs response length: r={r:.2f} p={p:.3f}")