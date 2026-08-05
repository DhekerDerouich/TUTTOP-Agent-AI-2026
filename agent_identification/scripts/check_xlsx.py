import pandas as pd

d = pd.read_excel("data/veille.xlsx", sheet_name=None, engine="openpyxl")
for k, v in d.items():
    print(f"=== {k} ({len(v)} rows) ===")
    for _, r in v.iterrows():
        nom = str(r.get("nom", "?"))[:40]
        dd = str(r.get("date_debut", ""))
        df = str(r.get("date_fin", ""))
        url = str(r.get("url", ""))[:50]
        sc = str(r.get("score_strategique", ""))
        print(f"  {nom:40s} date={dd:12s} fin={df:12s} score={sc:4s} url={url}")
