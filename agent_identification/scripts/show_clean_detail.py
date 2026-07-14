import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

df_h = pd.read_csv(
    DATA / "veille_hackathons.csv", dtype=str, encoding="utf-8-sig"
).fillna("")
print(f"HACKATHONS: {len(df_h)}\n")
for _, r in df_h.iterrows():
    u = r["url"].strip()
    if len(u) > 70:
        u = u[:70] + "..."
    print(f"  [{r['score_strategique']}/10] {r['nom'][:55]:55s}")
    print(f"       lieu={r['lieu'][:40]:40s} date={r['date_debut']:12s} url={u}")
    print()

df_e = pd.read_csv(
    DATA / "veille_evenements.csv", dtype=str, encoding="utf-8-sig"
).fillna("")
print(f"EVENEMENTS: {len(df_e)}\n")
for _, r in df_e.iterrows():
    u = r["url"].strip()
    if len(u) > 70:
        u = u[:70] + "..."
    print(f"  [{r['score_strategique']}/10] {r['nom'][:55]:55s}")
    print(f"       lieu={r['lieu'][:40]:40s} date={r['date']:12s} url={u}")
    print()
