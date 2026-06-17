"""Prepare URL list from existing XLSX."""

import pandas as pd
from pathlib import Path

d = Path(__file__).parent.parent / "data"
xlsx = d / "prospect_chauds.xlsx"
csv_out = d / "urls_a_verifier.csv"

df = pd.read_excel(xlsx, dtype=str).fillna("")
urls = df[df["site_web"] != ""][["site_web", "domaine"]].drop_duplicates()
urls.to_csv(csv_out, index=False, encoding="utf-8-sig")
print(f"Exported {len(urls)} URLs -> {csv_out}")
