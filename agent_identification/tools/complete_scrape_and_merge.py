"""Complete Phase 1 scraping + Phase 3 merge, skip Phase 2.
Usage: python tools/complete_scrape_and_merge.py
"""

import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
XLSX_IN = DATA / "prospect_chauds.xlsx"
XLSX_OUT = DATA / "prospect_chauds.xlsx"
CACHE_FILE = DATA / "cache_emails.json"

WORKERS = 50
TIMEOUT = 6
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
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
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    tmp.replace(CACHE_FILE)


def is_ce_email(email):
    return bool(re.match(r"^ce\.\w+@ac-", email, re.I))


def extract_emails(text):
    found = set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text))
    skip_ext = {".png", ".jpg", ".gif", ".svg", ".css", ".js", ".ico"}
    return {
        e.lower()
        for e in found
        if not any(e.lower().endswith(ext) for ext in skip_ext)
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
            if a["href"].startswith("mailto:"):
                e = a["href"][7:].split("?")[0].strip()
                if e and "@" in e:
                    result["mailto_emails"].append(e.lower())
        text = soup.get_text(separator=" ", strip=True)
        result["text_emails"] = sorted(extract_emails(text))
        all_e = set(result["mailto_emails"]) | set(result["text_emails"])
        result["emails"] = sorted(all_e)
        result["status"] = "ok"
    except Exception as e:
        result["status"] = str(e)[:100]
    return result


def complete_phase1(df, cache):
    to_scrape = []
    for _, row in df.iterrows():
        url = row.get("site_web", "")
        domaine = row.get("domaine", "")
        if not url or url == "nan":
            continue
        if (
            domaine in cache
            and cache[domaine].get("homepage", {}).get("status") == "ok"
        ):
            continue
        to_scrape.append((domaine, url))

    if not to_scrape:
        print("Phase 1: complet !")
        return cache

    print(f"Phase 1: {len(to_scrape)} sites restants...")
    done, t0 = 0, time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        fut_map = {
            pool.submit(lambda d, u: (d, scrape_homepage(u)), d, u): d
            for d, u in to_scrape
        }
        for fut in as_completed(fut_map):
            d = fut_map[fut]
            try:
                _, res = fut.result()
                if d not in cache:
                    cache[d] = {}
                cache[d]["homepage"] = res
            except:
                pass
            done += 1
            if done % 200 == 0:
                save_cache(cache)
                print(f"  {done}/{len(to_scrape)}  ({time.time() - t0:.0f}s)")

    save_cache(cache)
    print(f"Phase 1 OK: {done} sites en {time.time() - t0:.0f}s")
    return cache


def merge(df, cache):
    print("\nMerge emails...")
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

    mask = df["email_type"] == "humain"
    df.loc[mask, "email"] = df.loc[mask, "email_humain"]

    total = len(df)
    remplace = mask.sum()
    print(f"Emails remplaces: {remplace} / {total} ({remplace / total * 100:.1f}%)")
    rne = (df["email_type"] == "rne").sum()
    print(f"ce.xxx restants: {rne} ({rne / total * 100:.1f}%)")
    aucun = (df["email_type"] == "aucun").sum()
    print(f"Sans email: {aucun} ({aucun / total * 100:.1f}%)")

    df["_order"] = df["type"].apply(lambda t: 0 if "Prive" in str(t) else 1)
    df = df.sort_values(["_order", "score"], ascending=[True, False]).reset_index(
        drop=True
    )
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
    return df[cols]


def main():
    print("=" * 60)
    print("COMPLETE SCRAPE + MERGE EMAILS")
    print("=" * 60)

    df = pd.read_excel(XLSX_IN, dtype=str).fillna("")
    print(f"{len(df)} lignes, {df['site_web'].notna().sum()} avec site_web")

    cache = load_cache()
    print(f"Cache: {len(cache)} domaines")

    cache = complete_phase1(df, cache)
    df = merge(df, cache)

    df.to_excel(XLSX_OUT, index=False, engine="openpyxl")
    print(
        f"\nFINAL: {XLSX_OUT} ({len(df)} lignes, {XLSX_OUT.stat().st_size / 1024:.0f} Ko)"
    )


if __name__ == "__main__":
    main()
