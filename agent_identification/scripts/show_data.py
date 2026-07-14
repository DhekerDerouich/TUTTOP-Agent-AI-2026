import pandas as pd

df = pd.read_csv("data/veille_hackathons.csv", dtype=str, encoding="utf-8-sig").fillna(
    ""
)
print(f"HACKATHONS: {len(df)}")
for _, r in df.iterrows():
    u = r["url"].strip()
    if len(u) > 70:
        u = u[:70] + "..."
    print(f"  [{r['score_strategique']}/10] {r['nom'][:55]:55s} | {u}")

df = pd.read_csv("data/veille_evenements.csv", dtype=str, encoding="utf-8-sig").fillna(
    ""
)
print(f"\nEVENEMENTS: {len(df)}")
for _, r in df.iterrows():
    u = r["url"].strip()
    if len(u) > 70:
        u = u[:70] + "..."
    print(f"  [{r['score_strategique']}/10] {r['nom'][:55]:55s} | {u}")
