import pandas as pd
from pathlib import Path
from core.deduplicator import deduplicate
from models import Prospect

DATA_DIR = Path(__file__).parent / "data"
COUNTRIES = ["france", "belgique", "suisse", "tunisie"]
MODES = ["csv", "api", "web", "all"]


def load_all_prospects() -> dict[str, list[dict]]:
    by_country: dict[str, list[dict]] = {c: [] for c in COUNTRIES}
    pattern_modes = [f"prospects_{m}_" for m in MODES]

    for f in DATA_DIR.glob("prospects_*.csv"):
        if f.stem == "prospects_bruts_old":
            continue
        matched = False
        for prefix in pattern_modes:
            if f.stem.startswith(prefix):
                pays = f.stem[len(prefix) :]
                if pays in by_country:
                    matched = True
                    break
        if not matched:
            print(f"  Ignore {f.name} (pattern non reconnu)")
            continue

        try:
            df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
            df = df.fillna("")
            records = df.to_dict("records")
            count_before = len(by_country[pays])
            seen = set()
            for r in records:
                r["pays"] = r.get("pays", pays)
                key = (r.get("site_web", ""), r.get("nom", ""))
                if key not in seen:
                    seen.add(key)
                    by_country[pays].append(r)
            new_count = len(by_country[pays]) - count_before
            print(f"  {f.name}: {new_count} prospects -> {pays}")
        except Exception as e:
            print(f"  Erreur lecture {f.name}: {e}")

    return by_country


def clean_website(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    url = url.rstrip("/")
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("www."):
        return f"https://{url}"
    return url


def is_low_quality(url: str) -> bool:
    low = [
        "linkedin",
        "tiktok",
        "facebook",
        "instagram",
        "youtube",
        "twitter.com",
        "x.com",
        "pinterest",
        "google.com/maps",
        "googleadservices",
        "wikipedia",
        "wikidata",
        "annuaire",
        "annuaire",
        "yellowpages",
        "pagesjaunes",
        "search.ch",
        "iamexpat.ch",
        "schoolandcollegelistings",
        "info-maman.com",
        "a9racadabra.com",
        "africabizinfo.com",
        "ween.tn",
        "edelweiss-education.ch",
        "avdep.ch",
        "genevefamille.ch",
        "editions-bienvivre.ch",
        "travailler-en-suisse.ch",
        "francaisdesuisse.ch",
        "htr.ch",
        "universityguru.com",
        "zhkath.ch",
        "zh.ch",
        "ecoles.com.tn",
        "connect.bam.ch",
        "swisseducation.com",
        "ib-schools.com",
        "world-schools.com",
        "bestschool.tn",
    ]
    return any(s in url.lower() for s in low)


def dedup_records(records: list[dict]) -> list[dict]:
    seen_keys = set()
    result = []
    for r in records:
        web = r.get("site_web", "").strip().lower() if r.get("site_web") else ""
        nom = r.get("nom", "").strip().lower() if r.get("nom") else ""
        key = web if web else nom
        if key and key not in seen_keys:
            seen_keys.add(key)
            result.append(r)
    return result


def sort_prospects(records: list[dict]) -> list[dict]:
    def sort_key(r):
        has_web = 0 if r.get("site_web") and not is_low_quality(r["site_web"]) else 1
        has_email = 0 if r.get("email") else 1
        return (has_web, has_email)

    records.sort(key=sort_key)
    return records


def export_final(pays: str, records: list[dict]):
    out_path = DATA_DIR / f"{pays}_final.csv"
    for r in records:
        if r.get("site_web"):
            r["site_web"] = clean_website(r["site_web"])
        r["pays"] = pays.capitalize()

    records = dedup_records(records)
    records = sort_prospects(records)

    total = len(records)
    with_website = sum(1 for r in records if r.get("site_web"))
    with_email = sum(1 for r in records if r.get("email"))
    prive = sum(
        1 for r in records if "Priv" in r.get("type", "") or r.get("type") == "Privé"
    )
    public = sum(
        1 for r in records if "Pub" in r.get("type", "") or r.get("type") == "Public"
    )

    df = pd.DataFrame(records)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n{pays.capitalize()}: {total} prospects exportes")
    print(f"  - Prive: {prive} | Public: {public}")
    print(f"  - Avec site web: {with_website} | Avec email: {with_email}")
    print(f"  -> {out_path}")


def main():
    print("=== Generation des datasets finaux par pays ===\n")
    by_country = load_all_prospects()

    for pays in COUNTRIES:
        if by_country[pays]:
            export_final(pays, by_country[pays])
        else:
            print(f"\n{pays.capitalize()}: aucun prospect trouve")

    print("\n=== Termine ===")


if __name__ == "__main__":
    main()
