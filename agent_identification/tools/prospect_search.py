import pandas as pd
from pathlib import Path
from typing import Optional
from models import Prospect, SchoolType


FRANCE_CSV = (
    Path(__file__).parent.parent.parent / "france" / "fr-en-annuaire-education.csv"
)
TUNISIE_CSV = (
    Path(__file__).parent.parent.parent
    / "tunisie"
    / "tous_etablissements_avec_sites_web.csv"
)


def search_french_schools(
    statut: Optional[str] = None, departement: Optional[str] = None, limit: int = 50
) -> list[dict]:
    if not FRANCE_CSV.exists():
        return [{"error": "Fichier annuaire France non trouve"}]

    df = pd.read_csv(FRANCE_CSV, sep=";", dtype=str)
    df = df.fillna("")

    if statut:
        statut_clean = statut.lower().replace("é", "e")
        mask = (
            df["Statut_public_prive"]
            .astype(str)
            .str.lower()
            .str.replace("é", "e", regex=False)
            .str.contains(statut_clean, na=False)
        )
        df = df[mask]
    if departement:
        df = df[df["Code_departement"] == departement]

    has_web = df["Web"].notna() & (df["Web"].str.strip() != "")
    df = pd.concat([df[has_web], df[~has_web]])

    results = []
    for _, row in df.head(limit).iterrows():
        results.append(
            {
                "nom": row.get("Nom_etablissement", ""),
                "type": "Privé"
                if "Priv" in row.get("Statut_public_prive", "")
                else "Public",
                "localisation": f"{row.get('Nom_commune', '')}, {row.get('Libelle_departement', '')}",
                "site_web": row.get("Web", ""),
                "email": row.get("Mail", ""),
                "telephone": row.get("Telephone", ""),
                "source": "annuaire_france",
                "pays": "France",
            }
        )

    return results


def search_tunisian_schools(
    statut: Optional[str] = None, limit: int = 50
) -> list[dict]:
    if not TUNISIE_CSV.exists():
        return [{"error": "Fichier Tunisie non trouve"}]

    df = pd.read_csv(TUNISIE_CSV, dtype=str)
    df = df.fillna("")

    if statut:
        statut_clean = statut.lower().replace("é", "e")
        mask = (
            df["statut"]
            .astype(str)
            .str.lower()
            .str.replace("é", "e", regex=False)
            .str.contains(statut_clean, na=False)
        )
        df = df[mask]

    results = []
    for _, row in df.head(limit).iterrows():
        results.append(
            {
                "nom": row.get("nom", ""),
                "type": row.get("statut", ""),
                "localisation": f"{row.get('ville', '')}, Tunisie",
                "site_web": row.get("site_web", ""),
                "email": row.get("email", ""),
                "telephone": row.get("telephone", ""),
                "source": "annuaire_tunisie",
                "pays": "Tunisie",
            }
        )

    return results
