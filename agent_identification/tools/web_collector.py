import requests
from bs4 import BeautifulSoup
import urllib.parse
from core.extractor import normalize_prospect


SEARCH_QUERIES = [
    "liste des ecoles privees {pays}",
    "annuaire etablissements scolaires {pays}",
    "ecoles privees {pays} site officiel",
    "directory private schools {pays}",
    "liste lycees prives {pays}",
]

ANNUAIRES = [
    {
        "url": "https://www Ecoles privees france",
        "pays": "France",
        "type_lien": "annuaire",
    },
]


def search_web(query: str, max_results: int = 10) -> list[dict]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={max_results}"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if href.startswith("/url?q="):
                href = urllib.parse.unquote(href.split("/url?q=")[1].split("&")[0])
            if title and href.startswith("http") and len(title) > 10:
                results.append({"titre": title, "url": href})
        return results[:max_results]
    except Exception as e:
        print(f"  Erreur recherche web: {e}")
        return []


def scrape_directory_page(url: str, pays: str) -> list[dict]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        schools = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if (
                text
                and len(text) > 5
                and any(
                    kw in href.lower()
                    for kw in [
                        "ecole",
                        "school",
                        "etablissement",
                        "lycee",
                        "college",
                        "universite",
                    ]
                )
            ):
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    parsed = urllib.parse.urlparse(url)
                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    continue

                if full_url.count("/") <= 4:
                    continue

                schools.append(
                    {
                        "nom": text,
                        "site_web": full_url,
                        "ville": "",
                        "type": "Inconnu",
                    }
                )

        print(f"  Scrape {url}: {len(schools)} liens trouves")
        return schools[:30]
    except Exception as e:
        print(f"  Erreur scrape {url}: {e}")
        return []


def collect_from_web(statut: str | None = None, limit: int = 50) -> list[dict]:
    all_results = []

    search_terms = []
    for pays in ["France", "Belgique", "Suisse"]:
        for q in SEARCH_QUERIES:
            search_terms.append((pays, q.format(pays=pays)))

    for pays, query in search_terms:
        print(f"  Recherche web: [{pays}] {query}")
        results = search_web(query, max_results=5)
        for r in results:
            url = r["url"]
            scraped = scrape_directory_page(url, pays)
            for s in scraped:
                s["pays"] = pays
                s["departement"] = ""
                s["source"] = "web_scrape"
                s["email"] = ""
                s["telephone"] = ""
                if statut:
                    if "Priv" in statut and s.get("type") == "Public":
                        continue
                    if "Pub" in statut and s.get("type") == "Privé":
                        continue
                normalized = normalize_prospect(s, pays, "web_search")
                all_results.append(normalized)

        if len(all_results) >= limit:
            break

    return all_results[:limit]
