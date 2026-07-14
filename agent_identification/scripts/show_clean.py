import pandas as pd

df_h = pd.read_csv(
    "data/veille_hackathons_clean.csv", dtype=str, encoding="utf-8-sig"
).fillna("")
print(f"=== HACKATHONS ({len(df_h)}) ===")
for _, r in df_h.iterrows():
    print(
        f"  [{r['score_strategique']}/10] {r['nom'][:60]:60s} | {r['date_debut']:12s} | {r['lieu'][:30]:30s} | {r['url'][:80]}"
    )

df_e = pd.read_csv(
    "data/veille_evenements_clean.csv", dtype=str, encoding="utf-8-sig"
).fillna("")
print(f"\n=== EVENEMENTS ({len(df_e)}) ===")
for _, r in df_e.iterrows():
    print(
        f"  [{r['score_strategique']}/10] {r['nom'][:60]:60s} | {r['date']:12s} | {r['lieu'][:30]:30s} | {r['url'][:80]}"
    )
