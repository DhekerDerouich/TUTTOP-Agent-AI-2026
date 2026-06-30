from pathlib import Path
from datetime import datetime
import pandas as pd

DATA = Path(__file__).resolve().parent.parent.parent / "data"

PROSPECT_SOURCES = {
    "all": {
        "label": "Tous les prospects (120k)",
        "path": DATA / "all_data_enriched.csv",
        "type": "csv",
    },
    "chauds": {
        "label": "Prospects chauds (19k)",
        "path": DATA / "prospect_chauds.xlsx",
        "type": "xlsx",
    },
    "clean": {
        "label": "Prospects emails valides (8k)",
        "path": DATA / "prospect_chauds_clean.xlsx",
        "type": "xlsx",
    },
    "azur": {
        "label": "Azur (Nice/Cannes/Antibes/Menton)",
        "path": DATA / "prospect_azur.xlsx",
        "type": "xlsx",
    },
    "run": {
        "label": "Dernier run pipeline",
        "path": None,
        "type": "auto",
    },
}


def load_subventions() -> pd.DataFrame:
    path = DATA / "subventions_all.xlsx"
    if path.exists():
        return pd.read_excel(path)
    return pd.DataFrame()


def load_veille() -> dict[str, pd.DataFrame]:
    for name in ("veille.xlsx", "veille_final.xlsx", "veille_unified.xlsx"):
        path = DATA / name
        if path.exists():
            return pd.read_excel(path, sheet_name=None)
    return {}


def _find_latest_run_csv() -> Path | None:
    csvs = sorted(DATA.glob("prospects_all_*.csv"))
    return csvs[-1] if csvs else None


def get_prospect_source_info(key: str) -> dict:
    if key == "run":
        p = _find_latest_run_csv()
        if p is None:
            return {"label": "Aucun run trouvé", "path": "", "date": None, "rows": 0}
        rows = sum(1 for _ in open(p, encoding="utf-8", errors="replace")) - 1
        return {
            "label": f"Run pipeline {p.name}",
            "path": p.name,
            "date": datetime.fromtimestamp(p.stat().st_mtime),
            "rows": rows,
        }
    info = PROSPECT_SOURCES.get(key)
    if info is None:
        return {"label": "Inconnu", "path": "", "date": None, "rows": 0}
    p = info["path"]
    if not p or not p.exists():
        return {"label": info["label"], "path": "", "date": None, "rows": 0}
    if info["type"] == "xlsx":
        rows = len(pd.read_excel(p))
    else:
        rows = sum(1 for _ in open(p, encoding="utf-8", errors="replace")) - 1
    return {
        "label": info["label"],
        "path": p.name,
        "date": datetime.fromtimestamp(p.stat().st_mtime),
        "rows": rows,
    }


def load_prospects(key: str = "chauds") -> pd.DataFrame:
    if key == "run":
        p = _find_latest_run_csv()
        if p:
            return pd.read_csv(p, dtype=str)
        return pd.DataFrame()

    info = PROSPECT_SOURCES.get(key)
    if info is None:
        return pd.DataFrame()

    p = info["path"]
    if not p or not p.exists():
        return pd.DataFrame()

    if info["type"] == "xlsx":
        return pd.read_excel(p)
    return pd.read_csv(p, dtype=str)


def prospect_sources_available() -> list[str]:
    available = []
    for key, info in PROSPECT_SOURCES.items():
        if key == "run":
            if _find_latest_run_csv():
                available.append(key)
        else:
            p = info["path"]
            if p and p.exists():
                available.append(key)
    return available


def list_veille_csvs() -> list[Path]:
    return sorted(DATA.glob("veille*.csv"))


def list_prospects_csvs() -> list[Path]:
    return sorted(DATA.glob("prospects_*.csv"))


def list_final_csvs() -> list[Path]:
    return sorted(DATA.glob("*_final.csv"))


def load_contacts() -> pd.DataFrame:
    path = DATA / "contacts.csv"
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame()


def get_contacts_for_domaine(domaine: str) -> pd.DataFrame:
    contacts = load_contacts()
    if contacts.empty or "domaine" not in contacts.columns:
        return pd.DataFrame()
    return contacts[contacts["domaine"] == domaine].copy()
