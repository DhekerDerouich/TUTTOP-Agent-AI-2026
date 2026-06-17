import os
import re
import json
import time
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
APOLLO_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
BASE_DELAY = 5

PERSON_TITLES = [
    "directeur",
    "directrice",
    "principal",
    "proviseur",
    "headmaster",
    "head of school",
    "school director",
    "chef d'établissement",
    "responsable pédagogique",
    "directeur pédagogique",
    "directeur des études",
    "academic director",
    "head of teaching",
    "curriculum coordinator",
    "directeur innovation",
    "responsable it",
    "cto",
    "chief technology officer",
    "digital learning manager",
    "directeur numérique",
    "it manager",
    "responsable système d'information",
    "directeur des systèmes d'information",
    "directeur digital",
    "directeur du numérique",
    "directeur de la transformation digitale",
    "innovation manager",
]

GENERIC_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "laposte.net",
    "free.fr",
    "orange.fr",
    "wanadoo.fr",
    "sfr.fr",
    "aol.com",
    "live.fr",
    "msn.com",
    "icloud.com",
}

FRENCH_ACADEMIES = [
    "ac-aix-marseille.fr",
    "ac-amiens.fr",
    "ac-besancon.fr",
    "ac-bordeaux.fr",
    "ac-caen.fr",
    "ac-clermont-ferrand.fr",
    "ac-corse.fr",
    "ac-creteil.fr",
    "ac-dijon.fr",
    "ac-grenoble.fr",
    "ac-guadeloupe.fr",
    "ac-guyane.fr",
    "ac-lille.fr",
    "ac-limoges.fr",
    "ac-lyon.fr",
    "ac-martinique.fr",
    "ac-mayotte.fr",
    "ac-montpellier.fr",
    "ac-nancy-metz.fr",
    "ac-nantes.fr",
    "ac-nice.fr",
    "ac-normandie.fr",
    "ac-orleans-tours.fr",
    "ac-paris.fr",
    "ac-poitiers.fr",
    "ac-reims.fr",
    "ac-rennes.fr",
    "ac-reunion.fr",
    "ac-strasbourg.fr",
    "ac-toulouse.fr",
    "ac-versailles.fr",
]

NON_FR_DOMAINS = [
    "enseignement.be",
    "cfwb.be",
    "edubs.ch",
    "edu-ge.ch",
    "edu-vd.ch",
    "swissprivate-schools.ch",
    "education.gov.tn",
    "istruzione.it",
    "educacion.es",
    "schule.de",
    "schulen.de",
    "bildung.de",
    "edu.pt",
    "education.lu",
    "bildung.at",
]


def _extract_domain(site_web):
    if not site_web or site_web == "nan" or pd.isna(site_web):
        return None
    s = str(site_web).strip()
    if not s:
        return None
    if not s.startswith("http"):
        s = "https://" + s
    try:
        domain = urlparse(s).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain in GENERIC_DOMAINS:
            return None
        return domain
    except Exception:
        return None


def _is_academy(domain):
    return bool(re.search(r"ac-[a-z-]+\.fr$", domain))


def _normalize_domain(domain):
    m = re.search(r"(ac-[a-z-]+\.fr)$", domain)
    return m.group(1) if m else domain


def _call_api(payload):
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }
    payload["api_key"] = APOLLO_API_KEY
    try:
        resp = requests.post(
            APOLLO_SEARCH_URL, json=payload, headers=headers, timeout=20
        )
        if resp.status_code == 200:
            return resp.json().get("people", [])
        return None
    except Exception:
        return None


def _search_domain(domain):
    people = _call_api(
        {
            "organization_domains": [domain],
            "person_titles": PERSON_TITLES,
            "per_page": 10,
        }
    )
    if people is None:
        return None
    contacts = []
    for p in people:
        org = p.get("organization") or {}
        contacts.append(
            {
                "domaine": domain,
                "contact_nom": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "contact_prenom": p.get("first_name", ""),
                "contact_titre": p.get("title", ""),
                "linkedin_url": p.get("linkedin_url", ""),
                "apollo_id": p.get("id", ""),
                "organisation": org.get("name", ""),
                "secteur": org.get("industry", ""),
            }
        )
    return contacts


def _search_country(country):
    people = _call_api(
        {
            "q_organization_name": "school education",
            "organization_keyword_search": "school",
            "person_titles": PERSON_TITLES,
            "person_locations": [country],
            "per_page": 10,
        }
    )
    if people is None:
        return None
    contacts = []
    for p in people:
        org = p.get("organization") or {}
        contacts.append(
            {
                "domaine": f"country:{country}",
                "contact_nom": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "contact_prenom": p.get("first_name", ""),
                "contact_titre": p.get("title", ""),
                "linkedin_url": p.get("linkedin_url", ""),
                "apollo_id": p.get("id", ""),
                "organisation": org.get("name", ""),
                "secteur": org.get("industry", ""),
            }
        )
    return contacts


def run_apollo_collector(output="data/contacts_apollo.csv"):
    print("=" * 60)
    print("  APOLLO.IO - RECHERCHE DE CONTACTS")
    print("=" * 60)

    if not APOLLO_API_KEY:
        print("\n[ERR] APOLLO_API_KEY manquante dans .env")
        return

    data_path = Path(__file__).parent.parent / "data" / "all_data_enriched.csv"
    if not data_path.exists():
        print(f"[ERR] Fichier introuvable: {data_path}")
        return

    out_path = Path(__file__).parent.parent / output

    # Charger Chauds
    df = pd.read_csv(data_path, dtype=str).fillna("")
    chauds = df[df["qualification"] == "Chaud"]
    print(f"\nProspects Chauds: {len(chauds)}")

    # Extraire domaines
    domains = [_extract_domain(r.get("site_web", "")) for _, r in chauds.iterrows()]
    domains = [d for d in domains if d]
    cnt = Counter(domains)
    print(f"Domaines uniques: {len(cnt)}")

    # Separer academies vs prives
    academy_set = set()
    private_list = []
    for d, c in cnt.items():
        if _is_academy(d):
            academy_set.add(_normalize_domain(d))
        else:
            private_list.append((d, c))
    private_list.sort(key=lambda x: -x[1])

    phase1 = sorted(academy_set)[:35]
    phase1.extend([d for d in NON_FR_DOMAINS if d not in phase1][:15])
    phase2 = [d for d, _ in private_list[:200]]
    all_targets = phase1 + phase2

    print(f"\nPhase 1 (academies): {len(phase1)}")
    print(f"Phase 2 (top prives): {len(phase2)}")
    print(f"Total appels: {len(all_targets)}")
    print(f"Tps estime: {len(all_targets) * BASE_DELAY / 60:.1f} min\n")

    # Charger contacts deja trouves (reprise)
    existing = set()
    all_contacts = []
    if out_path.exists():
        old = pd.read_csv(out_path, dtype=str).fillna("")
        all_contacts = old.to_dict("records")
        existing = set(old.get("apollo_id", []))
        print(f"Reprise: {len(all_contacts)} contacts deja sauvegardes\n")

    processed = 0
    delay = BASE_DELAY
    consecutive_empty = 0
    saved_domains = set()
    start = time.time()

    def save():
        nonlocal all_contacts
        if all_contacts:
            pd.DataFrame(all_contacts).to_csv(
                out_path, index=False, encoding="utf-8-sig"
            )

    for domain in all_targets:
        # Deja fait ?
        if domain in saved_domains:
            continue
        saved_domains.add(domain)

        contacts = _search_domain(domain)
        processed += 1

        if contacts is None:
            delay = min(delay + 2, 15)
            print(
                f"  [{processed}/{len(all_targets)}] {domain:40s} -> ERREUR API, pause {delay}s"
            )
            time.sleep(delay)
            continue

        new = [c for c in contacts if c["apollo_id"] not in existing]
        all_contacts.extend(new)
        existing.update(c["apollo_id"] for c in new)

        if new:
            consecutive_empty = 0
            delay = max(BASE_DELAY, delay - 1)
            print(
                f"  [{processed}/{len(all_targets)}] {domain:40s} -> {len(new)} nouveaux contacts"
            )
        else:
            consecutive_empty += 1
            if consecutive_empty > 15:
                delay = max(delay + 1, BASE_DELAY)
                consecutive_empty = 0
            if processed <= 5 or processed % 20 == 0:
                print(f"  [{processed}/{len(all_targets)}] {domain:40s} -> 0 contact")

        # Sauvegarde incrementielle
        if processed % 25 == 0:
            save()

        elapsed = time.time() - start
        eta = (len(all_targets) - processed) * delay
        if processed % 25 == 0:
            print(
                f"  --- {processed}/{len(all_targets)} | total={len(existing)} | "
                f"{elapsed / 60:.1f}min | reste ~{eta / 60:.1f}min | pause={delay}s ---"
            )

        time.sleep(delay)

    # Sauvegarde finale
    save()
    total_time = (time.time() - start) / 60
    print(f"\n{'-' * 50}")
    print(f"  Termine en {total_time:.1f} min")
    print(f"  Contacts trouves: {len(all_contacts)}")

    if all_contacts:
        stats = pd.DataFrame(all_contacts)["contact_titre"].value_counts()
        print(f"\n  Top titres:")
        for t, c in stats.head(10).items():
            print(f"    {str(t)[:55]:55s} x{c}")
        print(f"\n  Fichier: {out_path}")


if __name__ == "__main__":
    run_apollo_collector()
