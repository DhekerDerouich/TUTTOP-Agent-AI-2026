from models import Prospect, SchoolType


ISO_TO_COUNTRY = {
    "FR": "France",
    "BE": "Belgique",
    "CH": "Suisse",
    "LU": "Luxembourg",
    "NL": "Pays-Bas",
    "ES": "Espagne",
    "PT": "Portugal",
    "IT": "Italie",
    "DE": "Allemagne",
    "AT": "Autriche",
    "PL": "Pologne",
    "CZ": "Tchequie",
    "HU": "Hongrie",
    "RO": "Roumanie",
    "GR": "Grece",
    "IE": "Irlande",
    "DK": "Danemark",
    "SE": "Suede",
    "NO": "Norvege",
    "FI": "Finlande",
    "GB": "Royaume-Uni",
    "LT": "Lituanie",
    "LV": "Lettonie",
    "EE": "Estonie",
    "SK": "Slovaquie",
    "SI": "Slovenie",
    "HR": "Croatie",
    "BG": "Bulgarie",
    "TN": "Tunisie",
}


def _extract_val(val) -> str:
    if isinstance(val, dict):
        return str(val.get("value", val.get("_value", "")))
    if val is None:
        return ""
    return str(val).strip()


def _extract_type(raw: dict) -> str:
    for key in ["type", "statut", "secteur", "schoolType", "school_type"]:
        val = _extract_val(raw.get(key))
        if "Priv" in val or "priv" in val.lower():
            return "Privé"
        if "Pub" in val or "pub" in val.lower():
            return "Public"
    return "Inconnu"


def _extract_localisation(raw: dict, pays: str) -> str:
    ville = _extract_val(
        raw.get("ville") or raw.get("city") or raw.get("addr:city") or ""
    )
    dept = _extract_val(raw.get("departement") or raw.get("region") or "")
    if ville:
        if dept:
            return f"{ville}, {dept}"
        return f"{ville}, {pays}"
    if dept:
        return f"{dept}, {pays}"
    return pays


def _extract_site_web(raw: dict) -> str:
    for key in ["site_web", "website", "web", "url", "siteweb", "www"]:
        val = _extract_val(raw.get(key))
        if val:
            if not val.startswith("http"):
                val = "https://" + val
            return val
    return ""


def _extract_email(raw: dict) -> str:
    for key in ["email", "mail", "e_mail", "contact_email", "courriel"]:
        val = _extract_val(raw.get(key))
        if val and "@" in val:
            return val
    return ""


def _extract_telephone(raw: dict) -> str:
    for key in ["telephone", "phone", "tel", "telefono", "telefoon", "contact_phone"]:
        val = _extract_val(raw.get(key))
        if val:
            return val
    return ""


def normalize_prospect(raw: dict, pays: str, source: str) -> dict:
    type_val = _extract_type(raw)
    localisation = _extract_localisation(raw, pays)
    site_web = _extract_site_web(raw)
    email = _extract_email(raw)
    telephone = _extract_telephone(raw)

    nom = ""
    for key in [
        "nom",
        "name",
        "schoolLabel",
        "title",
        "NAAM",
        "Nom_etablissement",
        "school",
        "ecole_nom",
    ]:
        val = _extract_val(raw.get(key))
        if val:
            nom = val
            break

    resolved_pays = pays
    pays_iso = _extract_val(raw.get("pays_iso") or raw.get("addr:country") or "")
    if pays_iso and pays_iso in ISO_TO_COUNTRY:
        resolved_pays = ISO_TO_COUNTRY[pays_iso]
    country_label = raw.get("countryLabel")
    if isinstance(country_label, dict) and country_label.get("value"):
        resolved_pays = country_label["value"]

    return {
        "nom": nom,
        "type": type_val,
        "localisation": localisation,
        "site_web": site_web,
        "email": email,
        "telephone": telephone,
        "source": source,
        "pays": resolved_pays,
    }
