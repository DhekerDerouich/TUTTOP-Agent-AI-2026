import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from core.extractor import normalize_prospect

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PRIVATE_KEYWORDS = [
    "prive",
    "privee",
    "privé",
    "privée",
    "hors contrat",
    "independante",
    "libre",
    "ecole libre",
]

_statut: str | None = None


def _is_private(text: str) -> bool:
    t = (
        text.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
    )
    return any(kw in t for kw in PRIVATE_KEYWORDS)


def _keep(priv: bool) -> bool:
    if _statut is None:
        return True
    s = _statut.lower().replace("é", "e").replace("è", "e")
    if "priv" in s:
        return priv
    if "public" in s:
        return not priv
    return True


def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, region="fr-fr"):
                results.append({"url": r["href"], "titre": r["title"]})
        if not results:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({"url": r["href"], "titre": r["title"]})
        return results
    except Exception as e:
        print(f"    DuckDuckGo erreur: {e}")
        return []


def _extract_from_detail(url: str) -> dict:
    info = {"email": "", "telephone": "", "site_web": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Try JSON-LD first (123ecoles has phone there)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(script.string)
                if isinstance(data, dict):
                    tel = data.get("telephone", "")
                    addr = data.get("address", {})
                    if isinstance(addr, dict):
                        tel = tel or addr.get("telephone", "")
                    if tel:
                        info["telephone"] = tel
                    web = data.get("url", "")
                    if web:
                        info["site_web"] = web
            except:
                pass

        # Extract from text (etablissements-scolaires has email)
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        for line in text.split("\n"):
            if len(line) < 20:
                continue
            if not info["email"]:
                m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", line)
                if m:
                    info["email"] = m.group()
            if not info["telephone"]:
                m = re.search(r"(0[1-9])(\s?\d{2}){4}", line.replace("\u00a0", " "))
                if m:
                    info["telephone"] = m.group().strip()
            if info["email"] and info["telephone"]:
                break

        # Extract real website from first external link
        if not info["site_web"]:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if (
                    href.startswith("http")
                    and "ecoles.com" not in href
                    and "etablissements-scolaires" not in href
                ):
                    if any(kw in href.lower() for kw in [".fr", ".com", ".org", ".eu"]):
                        info["site_web"] = href
                        break
    except:
        pass
    return info


def scrape_etablissements_scolaires(limit: int) -> list[dict]:
    results = []
    BASE = "http://etablissements-scolaires.fr"
    try:
        r = requests.get(f"{BASE}/departement.html", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        dept_links = [
            f"{BASE}/{a['href'].lstrip('/')}"
            for a in soup.find_all("a", href=True)
            if "departement-" in a["href"] and a["href"].endswith(".html")
        ][:8]
        for dept_url in dept_links:
            try:
                rd = requests.get(dept_url, headers=HEADERS, timeout=15)
                rd.raise_for_status()
                sd = BeautifulSoup(rd.text, "html.parser")
                city_links = [
                    f"{BASE}/{a['href'].lstrip('/')}"
                    for a in sd.find_all("a", href=True)
                    if "ville-" in a["href"]
                ][:5]
                for city_url in city_links:
                    try:
                        rc = requests.get(city_url, headers=HEADERS, timeout=15)
                        rc.raise_for_status()
                        sc = BeautifulSoup(rc.text, "html.parser")
                        for a in sc.find_all("a", href=True):
                            href = a["href"]
                            text = a.get_text(strip=True)
                            if "etablissement-scolaire-" in href and len(text) > 5:
                                private = _is_private(text)
                                if not _keep(private) and _statut:
                                    continue
                                full = (
                                    href
                                    if href.startswith("http")
                                    else f"{BASE}/{href.lstrip('/')}"
                                )
                                ville = (
                                    city_url.split("ville-")[-1]
                                    .replace(".html", "")
                                    .replace("-", " ")
                                    .title()
                                )
                                results.append(
                                    {
                                        "nom": text,
                                        "site_web": full,
                                        "ville": ville,
                                        "type": "Prive" if private else "Public",
                                        "email": "",
                                        "telephone": "",
                                        "pays": "France",
                                        "departement": "",
                                        "source": "annuaire_etablissements_scolaires",
                                    }
                                )
                                if len(results) >= limit:
                                    return results
                    except:
                        continue
            except:
                continue
    except Exception as e:
        print(f"    Erreur etablissements-scolaires.fr: {e}")
    return results


def scrape_123ecoles(limit: int) -> list[dict]:
    results = []
    BASE = "https://www.123ecoles.com"
    try:
        r = requests.get(
            f"{BASE}/etablissements-scolaires-par-departements/",
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        dept_urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "etablissements-scolaires-" in href and href.count("-") >= 2:
                dept_urls.append(href if href.startswith("http") else f"{BASE}{href}")
        dept_urls = dept_urls[:10]
        for dept_url in dept_urls:
            try:
                rd = requests.get(dept_url, headers=HEADERS, timeout=15)
                rd.raise_for_status()
                sd = BeautifulSoup(rd.text, "html.parser")
                for a in sd.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if (
                        "ecole-" in href or "lycee-" in href or "college-" in href
                    ) and len(text) > 10:
                        private = _is_private(text)
                        if not _keep(private) and _statut:
                            continue
                        full = href if href.startswith("http") else f"{BASE}{href}"
                        results.append(
                            {
                                "nom": text,
                                "site_web": full,
                                "ville": "",
                                "type": "Prive" if private else "Public",
                                "email": "",
                                "telephone": "",
                                "pays": "France",
                                "departement": "",
                                "source": "annuaire_123ecoles",
                            }
                        )
                        if len(results) >= limit:
                            return results
            except:
                continue
    except Exception as e:
        print(f"    Erreur 123ecoles.com: {e}")
    return results


def scrape_lesecoles(limit: int) -> list[dict]:
    results = []
    BASE = "https://lesecoles.fr"
    try:
        r = requests.get(BASE, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        region_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.count("/") == 1 and href.startswith("/") and len(href) > 3:
                if not any(
                    x in href.lower() for x in [".css", ".js", ".png", ".jpg", "#"]
                ):
                    region_links.append(f"{BASE}{href}")
        region_links = region_links[:5]
        for region_url in region_links:
            try:
                rr = requests.get(region_url, headers=HEADERS, timeout=15)
                rr.raise_for_status()
                sr = BeautifulSoup(rr.text, "html.parser")
                city_links = [
                    f"{BASE}{a['href']}"
                    for a in sr.find_all("a", href=True)
                    if a["href"].startswith("/")
                    and a["href"].count("-") >= 2
                    and len(a.get_text(strip=True)) > 5
                ][:3]
                for city_url in city_links:
                    try:
                        rc = requests.get(city_url, headers=HEADERS, timeout=15)
                        rc.raise_for_status()
                        sc = BeautifulSoup(rc.text, "html.parser")
                        for a in sc.find_all("a", href=True):
                            href = a["href"]
                            text = a.get_text(strip=True)
                            if (
                                href.startswith("/")
                                and "ecole" in href.lower()
                                and len(text) > 5
                            ):
                                private = _is_private(text)
                                if not _keep(private) and _statut:
                                    continue
                                full = f"{BASE}{href}"
                                results.append(
                                    {
                                        "nom": text,
                                        "site_web": full,
                                        "ville": "",
                                        "type": "Prive" if private else "Public",
                                        "email": "",
                                        "telephone": "",
                                        "pays": "France",
                                        "departement": "",
                                        "source": "annuaire_lesecoles",
                                    }
                                )
                                if len(results) >= limit:
                                    return results
                    except:
                        continue
            except:
                continue
    except Exception as e:
        print(f"    Erreur lesecoles.fr: {e}")
    return results


def scrape_ddg_results(limit: int) -> list[dict]:
    results = []
    queries = [
        "ecoles privees France site web",
        "ecole privee sous contrat annuaire",
        "private schools France directory",
    ]
    seen = set()
    for query in queries:
        sites = search_duckduckgo(query, max_results=5)
        for site in sites:
            url = site["url"]
            if url in seen:
                continue
            seen.add(url)
            try:
                r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if len(text) < 10:
                        continue
                    keywords = ["ecole", "lycee", "college", "institut", "prive"]
                    if not any(
                        kw in href.lower() or kw in text.lower() for kw in keywords
                    ):
                        continue
                    private = _is_private(text)
                    if not _keep(private) and _statut:
                        continue
                    if href.startswith("http"):
                        full_url = href
                    elif href.startswith("/"):
                        parsed = urllib.parse.urlparse(url)
                        full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                    else:
                        continue
                    results.append(
                        {
                            "nom": text,
                            "site_web": full_url,
                            "ville": "",
                            "type": "Prive" if private else "Public",
                            "email": "",
                            "telephone": "",
                            "pays": "France",
                            "departement": "",
                            "source": "web_recherche",
                        }
                    )
                    if len(results) >= limit:
                        return results
            except:
                continue
    return results


def collect_from_web(statut: str | None = None, limit: int = 50) -> list[dict]:
    global _statut
    _statut = statut
    all_results = []

    scrapers = [
        ("123ecoles.com", scrape_123ecoles),
        ("etablissements-scolaires.fr", scrape_etablissements_scolaires),
        ("lesecoles.fr", scrape_lesecoles),
        ("DuckDuckGo", scrape_ddg_results),
    ]

    for name, scraper_fn in scrapers:
        remaining = limit - len(all_results)
        if remaining <= 0:
            break
        print(f"  Scraping {name}...")
        try:
            results = scraper_fn(remaining)
            for s in results:
                normalized = normalize_prospect(s, s["pays"], s["source"])
                all_results.append(normalized)
            print(f"    -> {len(results)} prospects")
        except Exception as e:
            print(f"    Erreur: {e}")

    print(f"  Enrichissement (email/telephone/site web) depuis les pages detail...")
    enriched = 0
    for p in all_results[:limit]:
        detail_url = p.get("site_web", "")
        if not detail_url:
            continue
        if any(skip in detail_url for skip in ["web_recherche"]):
            continue
        info = _extract_from_detail(detail_url)
        if info["email"]:
            p["email"] = info["email"]
            enriched += 1
        if info["telephone"]:
            p["telephone"] = info["telephone"]
            enriched += 1
        if info["site_web"]:
            p["site_web"] = info["site_web"]
            enriched += 1
    if enriched:
        print(f"    -> {enriched} champs enrichis")

    print(f"  Total collecte web: {len(all_results)} prospects")
    return all_results[:limit]
