"""Nettoie la base prospects_tous_chauds."""

import re
import warnings
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

DATA = Path(__file__).parent.parent / "data"
IN = DATA / "prospects_tous_chauds.csv"
OUT = DATA / "prospect_chauds.xlsx"

print("=" * 60)
print("1. LECTURE")
print("=" * 60)
df = pd.read_csv(IN, dtype=str).fillna("")
print(f"  Lues: {len(df)} lignes")

# ── 2. DEDUP ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. DÉDUPLICATION")
print("=" * 60)
before = len(df)
df = df.drop_duplicates(subset=["nom", "localisation"], keep="first")
print(f"  Avant: {before}, Après: {len(df)}, Supprimés: {before - len(df)}")

# ── 3. NETTOYAGE ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. NETTOYAGE TEXTES")
print("=" * 60)


def clean_text(s):
    return re.sub(r"\s+", " ", str(s)).strip()


df["nom"] = df["nom"].apply(clean_text)
df["localisation"] = df["localisation"].apply(clean_text)
df["site_web"] = df["site_web"].apply(lambda s: str(s).strip())
df["email"] = df["email"].apply(lambda s: str(s).strip().lower())
df["telephone"] = df["telephone"].apply(clean_text)
df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype(int)
print("  OK")

# ── 4. DOMAINE ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. COLONNE DOMAINE")
print("=" * 60)


def extract_domain(site):
    if not site or site == "nan":
        return ""
    s = str(site).strip()
    if not s.startswith("http"):
        s = "https://" + s
    try:
        d = urlparse(s).netloc.lower()
        if d.startswith("www."):
            d = d[4:]
        return d
    except:
        return ""


df["domaine"] = df["site_web"].apply(extract_domain)
print(f"  Domaines extraits: {(df['domaine'] != '').sum()} / {len(df)}")

# ── 5. SUPPRIMER COLONNES ────────────────────────────────────
print("\n" + "=" * 60)
print("5. SUPPRESSION COLONNES")
print("=" * 60)
df = df.drop(columns=["source", "qualification"], errors="ignore")
print(f"  Colonnes: {list(df.columns)}")

# ── 6. TRI ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. TRI (Privé d'abord, score décroissant)")
print("=" * 60)
df["_order"] = df["type"].apply(lambda t: 0 if "Privé" in str(t) else 1)
df = df.sort_values(["_order", "score"], ascending=[True, False]).reset_index(drop=True)
df = df.drop(columns=["_order"])
print(
    f"  Privés: {(df['type'] == 'Privé').sum()} | Publics: {(df['type'] != 'Privé').sum()}"
)

# ── 7. EXPORT (sans site_valide pour l'instant) ──────────────
print("\n" + "=" * 60)
print("7. EXPORT XLSX")
print("=" * 60)
df.to_excel(OUT, index=False, engine="openpyxl")
print(f"  -> {OUT}")
print(f"  Lignes: {len(df)}")
print(f"  Taille: {OUT.stat().st_size / 1024:.0f} Ko")

# ── 8. EXPORT CSV POUR VÉRIF SITES ───────────────────────────
csv_out = DATA / "urls_a_verifier.csv"
urls = df[df["site_web"] != ""][["site_web", "domaine"]].drop_duplicates()
urls.to_csv(csv_out, index=False, encoding="utf-8-sig")
print(f"  URLs à vérifier: {len(urls)} → {csv_out}")

print("\n" + "=" * 60)
print("TERMINÉ ✓ — Lance maintenant la vérif des sites :")
print("  python tools/verifier_sites.py")
print("=" * 60)
