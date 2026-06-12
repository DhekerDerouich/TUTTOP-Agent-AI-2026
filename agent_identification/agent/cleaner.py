import re


def clean_site_web(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if ";" in url:
        url = url.split(";")[0].strip()
    url = url.rstrip("/")
    if url and not url.startswith("http"):
        url = "https://" + url
    return url


def clean_localisation(loc: str) -> str:
    if not loc or not isinstance(loc, str):
        return ""
    loc = loc.strip().strip(",").strip()
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    return ", ".join(parts)


def clean_telephone(tel: str) -> str:
    if not tel or not isinstance(tel, str):
        return ""
    tel = tel.strip()
    if tel.count("00 ") >= 2 and tel.count("  ") > 3:
        tel = tel.split("  ")[0]
    return tel


def deduplicate(records: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for r in records:
        nom = (r.get("nom") or "").strip().lower()
        pays = (r.get("pays") or "").strip().lower()
        site = (r.get("site_web") or "").strip().lower().rstrip("/")
        key = site if site else f"{nom}|{pays}"
        if key and key not in seen:
            seen.add(key)
            result.append(r)
    return result


def clean_prospects(records: list[dict]) -> list[dict]:
    print(f"  Nettoyage de {len(records)} prospects...")
    before = len(records)

    for r in records:
        r["site_web"] = clean_site_web(r.get("site_web", ""))
        r["localisation"] = clean_localisation(r.get("localisation", ""))
        r["telephone"] = clean_telephone(r.get("telephone", ""))
        if r.get("email") and isinstance(r["email"], str):
            r["email"] = r["email"].strip().lower()

    records = [r for r in records if r.get("nom")]
    records = deduplicate(records)

    after = len(records)
    print(f"  Supprime {before - after} (vides + doublons)")
    return records
