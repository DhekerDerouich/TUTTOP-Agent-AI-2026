"""Scraping massif des emails humains sur les sites prospect_chauds.

Phases:
  1. Homepage uniquement — extraire tous les mailto: et emails texte
  2. Pages equipe/direction — extraire noms, roles, LinkedIn (top schools)
  3. Merge dans prospect_chauds.xlsx — remplacer ce.xxx par emails humains

Usage:
  python tools/scraper_emails_massif.py
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
XLSX_IN = DATA / "prospect_chauds.xlsx"
XLSX_OUT = DATA / "prospect_chauds.xlsx"
CACHE = DATA / "cache_emails.json"

WORKERS_HOMEPAGE = 50
WORKERS_DEEP = 20
TIMEOUT = 6
DEEP_SCORE_MIN = 70

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

CHEMINS_EQUIPE = [
    "/equipe-pedagogique",
    "/organigramme",
    "/direction",
    "/notre-equipe",
    "/equipe",
    "/lequipe-pedagogique",
    "/lequipe",
    "/l-equipe",
    "/presentation",
    "/mot-du-directeur",
    "/mot-de-la-directrice",
    "/corps-enseignant",
    "/enseignants",
    "/equipe-educative",
    "/nos-equipes",
    "/gouvernance",
    "/staff",
    "/contact",
    "/a-propos",
    "/qui-sommes-nous",
    "/notre-ecole",
    "/ecole",
]

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


def load_cache():
    if CACHE.exists():
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    tmp.replace(CACHE)


def is_ce_email(email):
    return bool(re.match(r"^ce\.\w+@ac-", email, re.I))


def extract_emails(text):
    found = set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text))
    return {
        e.lower()
        for e in found
        if not any(
            e.lower().endswith(ext)
            for ext in [".png", ".jpg", ".gif", ".svg", ".css", ".js", ".ico"]
        )
        and "example" not in e
        and "placeholder" not in e
    }


def scrape_homepage(url):
    result = {
        "url": url,
        "emails": [],
        "mailto_emails": [],
        "text_emails": [],
        "status": "",
    }
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        if r.status_code != 200:
            result["status"] = f"HTTP {r.status_code}"
            return result
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if email and "@" in email:
                    result["mailto_emails"].append(email.lower())

        text = soup.get_text(separator=" ", strip=True)
        result["text_emails"] = sorted(extract_emails(text))
        all_e = set(result["mailto_emails"]) | set(result["text_emails"])
        result["emails"] = sorted(all_e)
        result["status"] = "ok"
    except Exception as e:
        result["status"] = str(e)[:100]
    return result


def scrape_team_pages(domaine, base_url):
    result = {"emails": set(), "noms": [], "linkedins": [], "pages": []}
    try:
        r = requests.get(base_url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        if r.status_code != 200:
            return result
    except:
        return result

    soup = BeautifulSoup(r.text, "html.parser")

    LINK_KW = [
        "equipe",
        "direction",
        "contact",
        "staff",
        "team",
        "organigramme",
        "gouvernance",
        "enseignant",
        "professeur",
        "presentation",
        "notre",
        "ecole",
        "a-propos",
        "about",
        "mot-du-directeur",
    ]

    team_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        txt = a.get_text(strip=True).lower()
        if any(kw in href or kw in txt for kw in LINK_KW):
            if a["href"].startswith("http"):
                team_urls.append(a["href"])
            else:
                team_urls.append(base_url.rstrip("/") + "/" + a["href"].lstrip("/"))

    for p in CHEMINS_EQUIPE:
        team_urls.append(base_url.rstrip("/") + p)

    seen = set()
    for tu in team_urls[:8]:
        if tu in seen:
            continue
        seen.add(tu)
        try:
            hr = requests.get(tu, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if hr.status_code != 200:
                continue
            result["pages"].append(tu)
            s2 = BeautifulSoup(hr.text, "html.parser")
            text2 = s2.get_text(separator=" ", strip=True)

            for a in s2.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    e = a["href"][7:].split("?")[0].strip().lower()
                    if e and "@" in e:
                        result["emails"].add(e)
            result["emails"] |= extract_emails(text2)

            for m in re.finditer(r"linkedin\.com/[a-zA-Z0-9_-]+", text2, re.I):
                result["linkedins"].append("https://" + m.group(0).lower())

            ROLES = [
                "directeur",
                "directrice",
                "proviseur",
                "principal",
                "chef",
                "responsable",
                "president",
                "presidente",
                "coordinateur",
                "coordinatrice",
                "secretaire",
            ]
            for role in ROLES:
                for m in re.finditer(
                    rf"(M\.|Mme|Ms|Mr|Monsieur|Madame|M\.me)\s+"
                    rf"([A-Za-zÀ-ÿéèêëùüûîïöôç]+(?:[\s-][A-Za-zÀ-ÿéèêëùüûîïöôç]+)?)",
                    text2,
                    re.I,
                ):
                    nom = m.group(2).strip()
                    if len(nom) > 2 and all(
                        n not in nom
                        for n in [
                            "Don",
                            "Bosco",
                            "Saint",
                            "Notre",
                            "Votre",
                            "Lyon",
                            "Paris",
                            "France",
                            "Contact",
                            "Email",
                        ]
                    ):
                        if nom not in [x["nom"] for x in result["noms"]]:
                            result["noms"].append(
                                {"nom": nom, "role": role.capitalize()}
                            )
        except:
            continue

    result["emails"] = sorted(result["emails"])
    return result


def phase1_homepages(df, cache):
    to_scrape = []
    for idx, row in df.iterrows():
        url = row.get("site_web", "")
        domaine = row.get("domaine", "")
        if not url or url == "nan":
            continue
        if (
            domaine in cache
            and cache[domaine].get("homepage", {}).get("status") == "ok"
        ):
            continue
        to_scrape.append((idx, domaine, url))

    if not to_scrape:
        print("Phase 1: rien a faire (tout en cache)")
        return cache

    print(f"Phase 1 — {len(to_scrape)} sites...")
    done = 0
    t0 = time.time()

    def worker(domaine, url):
        return domaine, scrape_homepage(url)

    with ThreadPoolExecutor(max_workers=WORKERS_HOMEPAGE) as pool:
        fut_map = {pool.submit(worker, d, u): d for _, d, u in to_scrape}
        for fut in as_completed(fut_map):
            domaine = fut_map[fut]
            try:
                _, res = fut.result()
                if domaine not in cache:
                    cache[domaine] = {}
                cache[domaine]["homepage"] = res
            except:
                pass
            done += 1
            if done % 500 == 0:
                save_cache(cache)
                elapsed = time.time() - t0
                print(f"  {done}/{len(to_scrape)}  ({elapsed:.0f}s)")

    save_cache(cache)
    elapsed = time.time() - t0
    print(f"Phase 1 OK: {done} sites en {elapsed:.0f}s")
    return cache


def phase2_deep(df, cache):
    to_scrape = []
    for idx, row in df.iterrows():
        url = row.get("site_web", "")
        domaine = row.get("domaine", "")
        score = row.get("score", 0)
        try:
            score = int(score)
        except:
            score = 0
        if not url or url == "nan":
            continue
        if score < DEEP_SCORE_MIN:
            continue
        if (
            domaine not in cache
            or cache[domaine].get("homepage", {}).get("status") != "ok"
        ):
            continue
        if domaine in cache and cache[domaine].get("deep", {}).get("pages"):
            continue
        to_scrape.append((idx, domaine, url, score))

    if not to_scrape:
        print("Phase 2: rien a faire")
        return cache

    print(f"Phase 2 — {len(to_scrape)} sites (score >= {DEEP_SCORE_MIN})...")
    done = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS_DEEP) as pool:
        fut_map = {pool.submit(scrape_team_pages, d, u): d for _, d, u, _ in to_scrape}
        for fut in as_completed(fut_map):
            domaine = fut_map[fut]
            try:
                res = fut.result()
                if domaine not in cache:
                    cache[domaine] = {}
                cache[domaine]["deep"] = {
                    "emails": res["emails"],
                    "noms": res["noms"],
                    "linkedins": list(set(res["linkedins"])),
                    "pages": res["pages"],
                }
            except:
                pass
            done += 1
            if done % 200 == 0:
                save_cache(cache)
                print(f"  {done}/{len(to_scrape)}  ({time.time() - t0:.0f}s)")

    save_cache(cache)
    print(f"Phase 2 OK: {done} sites en {time.time() - t0:.0f}s")
    return cache


def phase3_merge(df, cache):
    print("\nMerge des emails dans le DataFrame...")

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
        noms = []
        linkedins = []
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
            domain_part = e.split("@")[-1].lower() if "@" in e else ""
            if is_ce_email(e):
                continue
            if domain_part in IGNORED_DOMAINS:
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

    # Remplacer l'email par l'email humain si trouve
    mask = df["email_type"] == "humain"
    df.loc[mask, "email"] = df.loc[mask, "email_humain"]

    # Stats
    total = len(df)
    remplace = mask.sum()
    print(f"\nStats:")
    print(
        f"  Emails humains trouves: {remplace} / {total} ({remplace / total * 100:.1f}%)"
    )
    rne_restants = (df["email_type"] == "rne").sum()
    print(f"  ce.xxx restants: {rne_restants} ({rne_restants / total * 100:.1f}%)")
    aucun = (df["email_type"] == "aucun").sum()
    print(f"  Sans email: {aucun} ({aucun / total * 100:.1f}%)")

    return df


def main():
    print("=" * 60)
    print("SCRAPING MASSIF DES EMAILS")
    print("=" * 60)

    # Charger
    print("\n1. Chargement...")
    df = pd.read_excel(XLSX_IN, dtype=str).fillna("")
    print(f"   {len(df)} lignes")
    print(f"   {df['site_web'].notna().sum()} avec site_web")

    cache = load_cache()
    print(f"   Cache: {len(cache)} domaines")

    # Phase 1
    print("\n" + "=" * 60)
    print("PHASE 1: HOMEPAGES")
    print("=" * 60)
    cache = phase1_homepages(df, cache)

    # Phase 2
    print("\n" + "=" * 60)
    print("PHASE 2: PAGES EQUIPE")
    print("=" * 60)
    cache = phase2_deep(df, cache)

    # Phase 3
    print("\n" + "=" * 60)
    print("PHASE 3: MERGE + EXPORT")
    print("=" * 60)
    df = phase3_merge(df, cache)

    # Export
    df.to_excel(XLSX_OUT, index=False, engine="openpyxl")
    size_kb = XLSX_OUT.stat().st_size / 1024

    print(f"\n{'=' * 60}")
    print(f"FICHIER FINAL: {XLSX_OUT}")
    print(f"  Lignes: {len(df)}")
    print(f"  Taille: {size_kb:.0f} Ko")
    print(f"  Colonnes: {list(df.columns)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
