"""Re-merge and export (assumes cache is complete)."""

import json, re
from pathlib import Path
import pandas as pd

BASE = Path(__file__).parent.parent
DATA = BASE / "data"

df = pd.read_excel(DATA / "prospect_chauds_old.xlsx", dtype=str).fillna("")
print(f"{len(df)} lignes chargees")

with open(DATA / "cache_emails.json", encoding="utf-8") as f:
    cache = json.load(f)

IGNORED_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "laposte.net",
    "free.fr",
    "orange.fr",
    "wanadoo.fr",
    "sfr.fr",
    "live.fr",
    "live.com",
    "msn.com",
}


def is_ce_email(e):
    return bool(re.match(r"^ce\.\w+@ac-", e, re.I))


new_cols = {
    "emails_trouves": [],
    "email_humain": [],
    "email_type": [],
    "contact_nom": [],
    "contact_role": [],
    "linkedin": [],
}

for _, row in df.iterrows():
    domaine = row.get("domaine", "")
    email_orig = row.get("email", "")
    ce_orig = is_ce_email(email_orig)

    emails_scrapes = set()
    noms, linkedins = [], []
    if domaine in cache:
        hp = cache[domaine].get("homepage", {})
        dp = cache[domaine].get("deep", {})
        for e in hp.get("emails", []):
            emails_scrapes.add(e)
        for e in dp.get("emails", []):
            emails_scrapes.add(e)
        noms = dp.get("noms", [])
        linkedins = dp.get("linkedins", [])

    humains = []
    for e in emails_scrapes:
        dp_ = e.split("@")[-1].lower() if "@" in e else ""
        if is_ce_email(e) or dp_ in IGNORED_DOMAINS:
            continue
        humains.append(e)
    humains = sorted(set(humains))

    new_cols["emails_trouves"].append(
        " | ".join(sorted(emails_scrapes)) if emails_scrapes else ""
    )
    new_cols["email_humain"].append(humains[0] if humains else "")
    if humains:
        new_cols["email_type"].append("humain")
    elif email_orig and not ce_orig:
        new_cols["email_type"].append("original")
    elif email_orig:
        new_cols["email_type"].append("rne")
    else:
        new_cols["email_type"].append("aucun")
    new_cols["contact_nom"].append(noms[0]["nom"] if noms else "")
    new_cols["contact_role"].append(noms[0]["role"] if noms else "")
    new_cols["linkedin"].append(" | ".join(linkedins[:3]) if linkedins else "")

for col, vals in new_cols.items():
    df[col] = vals

mask = df["email_type"] == "humain"
df.loc[mask, "email"] = df.loc[mask, "email_humain"]

total = len(df)
print(
    f"\nEmails humains trouves: {mask.sum()} / {total} ({mask.sum() / total * 100:.1f}%)"
)
print(
    f"ce.xxx restants: {(df['email_type'] == 'rne').sum()} ({(df['email_type'] == 'rne').sum() / total * 100:.1f}%)"
)
print(
    f"Sans email: {(df['email_type'] == 'aucun').sum()} ({(df['email_type'] == 'aucun').sum() / total * 100:.1f}%)"
)

df["_order"] = df["type"].apply(lambda t: 0 if "Prive" in str(t) else 1)
df = df.sort_values(["_order", "score"], ascending=[True, False]).reset_index(drop=True)
df = df.drop(columns=["_order"])

cols = [
    "nom",
    "type",
    "localisation",
    "site_web",
    "email",
    "telephone",
    "pays",
    "score",
    "domaine",
    "site_valide",
    "emails_trouves",
    "email_type",
    "contact_nom",
    "contact_role",
    "linkedin",
]
cols = [c for c in cols if c in df.columns]

out = DATA / "prospect_chauds.xlsx"
df[cols].to_excel(out, index=False, engine="openpyxl")
print(
    f"\nExporte: {out} ({out.stat().st_size / 1024:.0f} Ko, {len(df)} lignes, {len(cols)} colonnes)"
)
print("Colonnes:", cols)
