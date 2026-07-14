import pandas as pd
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

SOCIAL_DOMAINS = {"instagram.com", "facebook.com", "tiktok.com", "youtube.com"}
LISTING_DOMAINS = {
    "conferenceindex.org",
    "internationalconferencealerts.com",
    "allconferencealert.net",
    "conferenceineurope.net",
    "easychair.org",
    "tradefest.io",
    "allhackathons.com",
    "devpost.com",
    "letudiant.fr",
    "eschoolnews.com",
    "gettingsmart.com",
    "panoramaed.com",
    "worldwide-edtech.org",
    "aspectusgroup.com",
    "simplifiediq.com",
}
LOW_QUALITY_NAMES = {
    "pas d'informations disponibles",
    "pas d'info",
    "non specifie",
    "string",
    "cfp",
    "hackathon inconnu",
    "inconnu",
}
LOW_QUALITY_URL_PATTERNS = [
    r"instagram\.com",
    r"facebook\.com",
    r"tiktok\.com",
    r"youtube\.com",
    r"fliphtml5\.com",
]


def is_low_quality(row, date_fields):
    nom = str(row.get("nom", "")).strip().lower()
    url = str(row.get("url", "")).strip().lower()
    lieu = str(row.get("lieu", "")).strip().lower()
    source = str(row.get("source", "")).strip().lower()
    score = pd.to_numeric(row.get("score_strategique", 0), errors="coerce")

    if nom in LOW_QUALITY_NAMES or not nom or nom == "nan":
        return True, "nom vide/générique"

    if not url or url == "nan" or url == "string":
        return True, "pas d'URL"

    for pat in LOW_QUALITY_URL_PATTERNS:
        if re.search(pat, url):
            return True, f"réseau social: {url[:50]}"

    for domain in LISTING_DOMAINS:
        if domain in url:
            return True, f"site listing: {domain}"

    # Generic site homepages masquerading as events
    generic_homepages = ["epitech.eu", "ionis-group.com", "vivatech.com", "riseup.ai"]
    for gh in generic_homepages:
        if url.rstrip("/") == f"https://{gh}" or url.rstrip("/") == f"https://www.{gh}":
            return True, f"page d'accueil: {gh}"

    # No date at all
    has_date = False
    for f in date_fields:
        val = str(row.get(f, "")).strip()
        if val and val not in ("nan", "", "0", "Pas d'informations disponibles"):
            has_date = True
    if not has_date and score < 5:
        return True, f"pas de date + score bas ({score})"

    # Score too low
    if score < 3:
        return True, f"score trop bas ({score})"

    return False, ""


def clean_file(filepath, date_fields, sheet_name):
    print(f"\nNettoyage: {filepath.name}")
    df = pd.read_csv(filepath, dtype=str, encoding="utf-8-sig").fillna("")
    print(f"  Entrees avant: {len(df)}")

    removed = []
    keep_mask = []
    for idx, row in df.iterrows():
        bad, reason = is_low_quality(row, date_fields)
        if bad:
            removed.append((idx, row.get("nom", ""), reason))
            keep_mask.append(False)
        else:
            keep_mask.append(True)

    df_clean = df[keep_mask].copy()
    print(f"  Entrees apres: {len(df_clean)}")
    print(f"  Supprimees: {len(removed)}")
    for idx, nom, reason in removed[:20]:
        print(f"    - [{reason}] {nom[:60]}")
    if len(removed) > 20:
        print(f"    ... et {len(removed) - 20} autres")

    return df_clean


# Clean hackathons
h_path = DATA / "veille_hackathons.csv"
e_path = DATA / "veille_evenements.csv"

df_h = clean_file(h_path, ["date_debut", "date_fin"], "Hackathons")
df_e = clean_file(e_path, ["date"], "Evenements")

# Save cleaned CSVs
out_h = DATA / "veille_hackathons_clean.csv"
out_e = DATA / "veille_evenements_clean.csv"
df_h.to_csv(out_h, index=False, encoding="utf-8-sig")
df_e.to_csv(out_e, index=False, encoding="utf-8-sig")
print(f"\nSauvegardes:")
print(f"  {out_h} ({len(df_h)} lignes)")
print(f"  {out_e} ({len(df_e)} lignes)")

# Generate clean XLSX
xlsx_path = DATA / "veille_clean.xlsx"
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    df_h.to_excel(writer, sheet_name="Hackathons", index=False)
    df_e.to_excel(writer, sheet_name="Evenements", index=False)
print(f"  {xlsx_path} genere")
