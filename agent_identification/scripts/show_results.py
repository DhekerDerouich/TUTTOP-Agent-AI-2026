import sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd

h = pd.read_csv("data/final_hackathons.csv", encoding="utf-8-sig")
e = pd.read_csv("data/final_evenements.csv", encoding="utf-8-sig")

print("=== HACKATHONS ===")
for _, r in h.iterrows():
    dd = str(r.get("date_debut", "") or "")
    df = str(r.get("date_fin", "") or "")
    if dd != "nan" and df != "nan":
        dates = f"{dd} -> {df}"
    elif dd != "nan":
        dates = dd
    else:
        dates = "pas de date"
    print(f"  [{r.score_strategique}/10] {str(r.nom)[:55]} | {dates}")

print()
print("=== EVENEMENTS ===")
for _, r in e.iterrows():
    d = str(r.get("date", "") or "")
    if d == "nan":
        d = "pas de date"
    print(f"  [{r.score_strategique}/10] {str(r.nom)[:55]} | {d}")

print()
print(f"Total: {len(h)} hackathons + {len(e)} evenements = {len(h) + len(e)}")
