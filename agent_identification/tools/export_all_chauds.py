import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
in_path = DATA_DIR / "all_data_enriched.csv"
out_path = DATA_DIR / "prospects_tous_chauds.csv"

df = pd.read_csv(in_path, dtype=str).fillna("")
chauds = df[df["qualification"] == "Chaud"].copy()
chauds.to_csv(out_path, index=False, encoding="utf-8-sig")

print(f"Total Chauds exportés: {len(chauds)}")
print(f"  Privés: {(chauds['type'] == 'Privé').sum()}")
print(f"  Publics: {(chauds['type'] != 'Privé').sum()}")
print(f"  Pays représentés: {chauds['pays'].nunique()}")
print(f"Fichier: {out_path}")
