from models import Prospect, SchoolType


def normalize_prospect(raw: dict, pays: str, source: str) -> dict:
    if isinstance(raw.get("type"), str):
        if "Priv" in raw["type"]:
            type_val = "Privé"
        elif "Pub" in raw["type"]:
            type_val = "Public"
        else:
            type_val = "Inconnu"
    else:
        type_val = "Inconnu"

    if isinstance(raw.get("ville"), str) and raw["ville"].strip():
        if isinstance(raw.get("departement"), str) and raw["departement"].strip():
            localisation = f"{raw['ville']}, {raw['departement']}"
        else:
            localisation = f"{raw['ville']}, {pays}"
    else:
        localisation = pays

    site_web = raw.get("site_web") or raw.get("web") or ""
    if isinstance(site_web, str):
        site_web = site_web.strip()
    else:
        site_web = ""

    email = raw.get("email") or raw.get("mail") or ""
    if isinstance(email, str):
        email = email.strip()
    else:
        email = ""

    telephone = raw.get("telephone") or ""
    if isinstance(telephone, str):
        telephone = telephone.strip()
    else:
        telephone = ""

    return {
        "nom": str(raw.get("nom", raw.get("name", ""))).strip(),
        "type": type_val,
        "localisation": localisation,
        "site_web": site_web,
        "email": email,
        "telephone": telephone,
        "source": source,
        "pays": pays,
    }
