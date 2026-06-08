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
_pays: str = "France"


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
        try:
            from ddgs import DDGS
        except:
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


def _is_skip_url(url: str) -> bool:
    skip = [
        "123ecoles.com",
        "etablissements-scolaires",
        "lesecoles.fr",
        "enseignement-prive.info",
        "ecoleprimaire.tn",
        "bestschool.tn",
        "swissprivate-schools.ch",
        "storage",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".css",
        ".js",
        "facebook",
        "twitter",
        "youtube",
        "instagram",
        "google.com/maps",
        "classe-decouverte",
        "linkedin",
        "tiktok",
        "pinterest",
        "wikipedia",
        "wikidata",
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
        "cookiedatabase.org",
        "copainsdavant",
        "bouke.media",
    ]
    return any(s in url.lower() for s in skip)


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
                    if web and not info["site_web"] and not _is_skip_url(web):
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
                line_clean = line.replace("\u00a0", " ")
                # French: 0X XX XX XX XX or +33 X XX XX XX XX
                m = re.search(r"(0[1-9])(\s?\d{2}){4}", line_clean)
                if not m:
                    # International: +32 (BE), +41 (CH), +216 (TN), +33 (FR)
                    m = re.search(
                        r"(\+|00)(32|41|216|33)\s?\d[\d\s\.\-]{6,12}", line_clean
                    )
                if not m:
                    # Generic: any country code + digits
                    m = re.search(r"(\+|00)\d{1,3}\s?\d[\d\s\.\-]{6,12}", line_clean)
                if m:
                    info["telephone"] = m.group().strip()
            if info["email"] and info["telephone"]:
                break

        # Extract real website from first external link (skip images, CSS, JS, directories)
        if not info["site_web"]:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http"):
                    continue
                if _is_skip_url(href):
                    continue
                if any(
                    kw in href.lower()
                    for kw in [".fr", ".be", ".ch", ".com", ".org", ".eu"]
                ):
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
                                        "pays": _pays,
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
                                "pays": _pays,
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
                                        "pays": _pays,
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


def _allowed_domains(pays: str) -> list[str]:
    ds = {
        "france": [".fr", ".org", ".com"],
        "belgique": [".be", ".eu", ".com"],
        "suisse": [".ch", ".eu", ".com"],
        "tunisie": [".tn", ".com", ".org"],
    }
    return ds.get(pays.lower(), [".fr", ".com"])


def _filter_country_url(url: str, pays: str) -> bool:
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    if not host:
        return True
    domains = _allowed_domains(pays)
    return any(host.endswith(d) for d in domains)


def _country_queries(pays: str) -> list[str]:
    qs = {
        "france": [
            "ecoles privees France site web",
            "ecole privee sous contrat annuaire",
        ],
        "belgique": [
            "ecoles privees Belgique site web",
            "site:.be ecole privee enseignement",
            "enseignement prive Belgique annuaire",
            "private schools Belgium site:.be",
        ],
        "suisse": [
            "ecoles privees Suisse site web",
            "site:.ch ecole privee enseignement",
            "private schools Switzerland site:.ch",
            "schulen Schweiz privat site:.ch",
        ],
        "tunisie": [
            "ecoles privees Tunisie site web",
            "site:.tn ecole privee enseignement",
            "private schools Tunisia site:.tn",
            "annuaire ecoles privees Tunisie",
        ],
    }
    return qs.get(pays.lower(), qs["france"])


def _extract_search_listing(a) -> dict | None:
    """Extract school name and city from an <a> tag listing."""
    href = a.get("href", "")
    if "/offre-emploi/" in href:
        return None
    text = a.get_text(separator=" ", strip=True)
    if len(text) < 5:
        return None
    parts = [t.strip() for t in text.split() if t.strip()]
    raw = " ".join(parts)
    ville = ""
    nom = raw
    # Try to find city + name pattern (e.g. "LochesCamp Basket 3x3" → ville="Loches", nom="Camp Basket 3x3")
    # Common French cities often appear first before the name
    known_cities = [
        "paris",
        "lyon",
        "marseille",
        "lille",
        "toulouse",
        "bordeaux",
        "loches",
        "tournai",
        "mouscron",
        "comines",
        "ramegnies",
        "chin",
        "lausanne",
        "geneve",
        "zurich",
        "bern",
        "basel",
        "vevey",
        "montreux",
        "villars",
        "gstaad",
        "la tour de peilz",
        "leysin",
        "chesieres",
        "neuchatel",
        "fribourg",
        "sion",
    ]
    first_word = parts[0].lower().rstrip(",") if parts else ""
    if first_word in known_cities:
        ville = parts[0].rstrip(",")
        nom = " ".join(parts[1:])
    return {"nom": nom, "ville": ville, "raw": raw}


def scrape_enseignement_prive(limit: int) -> list[dict]:
    results = []
    BASE = "https://www.enseignement-prive.info"
    country_paths = {
        "belgique": [
            "/onglet/ecole/belgique-990",
            "/onglet/college/belgique-990",
            "/onglet/lycee/belgique-990",
        ],
        "suisse": [
            "/onglet/ecole/suisse-991",
            "/onglet/college/suisse-991",
            "/onglet/lycee/suisse-991",
        ],
    }
    paths = country_paths.get(_pays.lower(), [])
    for path in paths:
        remaining = limit - len(results)
        if remaining <= 0:
            break
        try:
            r = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/fiche/" not in href or "/offre-emploi/" in href:
                    continue
                listing = _extract_search_listing(a)
                if not listing or not listing["nom"]:
                    continue
                full = href if href.startswith("http") else f"{BASE}{href}"
                results.append(
                    {
                        "nom": listing["nom"],
                        "site_web": full,
                        "ville": listing["ville"],
                        "type": "Prive",
                        "email": "",
                        "telephone": "",
                        "pays": _pays,
                        "departement": "",
                        "source": "annuaire_enseignement_prive",
                    }
                )
                if len(results) >= limit:
                    return results
        except Exception as e:
            print(f"    Erreur {path}: {e}")
    return results


def scrape_fabert_be(limit: int) -> list[dict]:
    results = []
    BASE = "https://www.fabert.com"
    for page in range(1, 3):
        remaining = limit - len(results)
        if remaining <= 0:
            break
        try:
            url = f"{BASE}/etablissement-prive/?country=Belgique&p={page}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.select(
                ".etablissement-item, .result-item, .bloc-resultat"
            ):
                nom_el = card.select_one("h3 a, .titre a, .nom a")
                tel_el = card.select_one(".telephone, .tel, [itemprop=telephone]")
                if not nom_el:
                    continue
                nom = nom_el.get_text(strip=True)
                href = nom_el.get("href", "")
                if not nom or len(nom) < 3:
                    continue
                full_url = href if href.startswith("http") else f"{BASE}{href}"
                tel = tel_el.get_text(strip=True) if tel_el else ""
                results.append(
                    {
                        "nom": nom,
                        "site_web": full_url,
                        "ville": "",
                        "type": "Prive",
                        "email": "",
                        "telephone": tel,
                        "pays": _pays,
                        "departement": "",
                        "source": "annuaire_fabert_be",
                    }
                )
                if len(results) >= limit:
                    return results
            if not results:
                break
        except Exception as e:
            print(f"    Erreur fabert.com page {page}: {e}")
    return results


def scrape_ecoleprimaire_tn(limit: int) -> list[dict]:
    results = []
    BASE = "https://www.ecoleprimaire.tn"
    city_pages = [
        "/ecoles/ecoles-primaires-privees-tunis/",
        "/ecoles/ecoles-primaires-privees-ariana/",
        "/ecoles/ecoles-primaires-privees-ben-arous/",
        "/ecoles/ecoles-primaires-privees-manouba/",
        "/ecoles/ecoles-primaires-privees-sfax/",
        "/ecoles/ecoles-primaires-privees-sousse/",
        "/ecoles/ecoles-primaires-privees-nabeul/",
        "/ecoles/ecoles-primaires-privees-bizerte/",
        "/ecoles/ecoles-primaires-privees-monastir/",
        "/ecoles/ecoles-primaires-privees-mahdia/",
    ]
    for city_path in city_pages:
        remaining = limit - len(results)
        if remaining <= 0:
            break
        try:
            r = requests.get(f"{BASE}{city_path}", headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for article in soup.find_all("article"):
                h2 = article.find(["h1", "h2", "h3"])
                a = article.find("a", href=True)
                if not h2 or not a:
                    continue
                nom = h2.get_text(strip=True)
                href = a["href"]
                if len(nom) < 3 or not href.startswith("http"):
                    continue
                if any(
                    x in href.lower() for x in ["facebook", "twitter", "bestschool"]
                ):
                    continue
                results.append(
                    {
                        "nom": nom,
                        "site_web": href,
                        "ville": city_path.split("privees-")[-1]
                        .rstrip("/")
                        .replace("-", " ")
                        .title(),
                        "type": "Prive",
                        "email": "",
                        "telephone": "",
                        "pays": _pays,
                        "departement": "",
                        "source": "annuaire_ecoleprimaire_tn",
                    }
                )
                if len(results) >= limit:
                    return results
        except Exception as e:
            print(f"    Erreur {city_path}: {e}")
    return results


def scrape_swiss_private_schools(limit: int) -> list[dict]:
    results = []
    BASE = "https://www.swissprivate-schools.ch"
    try:
        r = requests.get(f"{BASE}/fr/schools", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract school name+url from ItemList JSON-LD (50 schools)
        seen_urls = set()
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json

                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        school = item.get("item", {})
                        name = school.get("name", "")
                        url = school.get("url", "")
                        if (
                            name
                            and url
                            and url not in seen_urls
                            and not _is_skip_url(url)
                        ):
                            seen_urls.add(url)
                            results.append(
                                {
                                    "nom": name,
                                    "site_web": url,
                                    "ville": "",
                                    "type": "Prive",
                                    "email": "",
                                    "telephone": "",
                                    "pays": _pays,
                                    "departement": "",
                                    "source": "annuaire_swiss_private_schools",
                                }
                            )
                            if len(results) >= limit:
                                return results
            except:
                pass

        # Additional schools from navigation links (130+ total)
        if len(results) < limit:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if (
                    "/fr/schools/" in href
                    and href not in seen_urls
                    and not _is_skip_url(href)
                ):
                    seen_urls.add(href)
                    slug = href.rstrip("/").split("/")[-1]
                    name = slug.replace("-", " ").title()
                    if name and len(name) > 3:
                        full = href if href.startswith("http") else f"{BASE}{href}"
                        results.append(
                            {
                                "nom": name,
                                "site_web": full,
                                "ville": "",
                                "type": "Prive",
                                "email": "",
                                "telephone": "",
                                "pays": _pays,
                                "departement": "",
                                "source": "annuaire_swiss_private_schools",
                            }
                        )
                        if len(results) >= limit:
                            return results
    except Exception as e:
        print(f"    Erreur swissprivate-schools.ch: {e}")
    return results


def scrape_ddg_results(limit: int) -> list[dict]:
    results = []
    queries = _country_queries(_pays)
    seen = set()
    for query in queries:
        sites = search_duckduckgo(query, max_results=5)
        for site in sites:
            url = site["url"]
            if url in seen:
                continue
            if _is_skip_url(url) or not _filter_country_url(url, _pays):
                print(f"    (filtre) {url}")
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
                    if _is_skip_url(href):
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
                            "pays": _pays,
                            "departement": "",
                            "source": "web_recherche",
                        }
                    )
                    if len(results) >= limit:
                        return results
            except:
                continue
    return results


def _is_directory_url(url: str) -> bool:
    return any(
        d in url
        for d in [
            "123ecoles.com",
            "etablissements-scolaires",
            "lesecoles.fr",
            "enseignement-prive.info",
            "ecoleprimaire.tn",
            "bestschool.tn",
            "swissprivate-schools.ch",
            "storage",
        ]
    )


def _find_real_website(nom: str, ville: str = "", pays: str = "France") -> str:
    query = f"{nom} {ville} {pays}".strip()
    query = re.sub(r"\s+", " ", query)[:100]
    try:
        sites = search_duckduckgo(query, max_results=3)
        for site in sites:
            url = site["url"]
            if _is_skip_url(url):
                continue
            if _filter_country_url(url, pays) and any(
                kw in url.lower()
                for kw in [
                    "ecole",
                    "lycee",
                    "college",
                    "institut",
                    "school",
                    "schule",
                    "gymnasium",
                ]
            ):
                return url
    except:
        pass
    return ""


def _run_with_timeout(fn, args=(), kwargs=None, timeout_sec=120):
    kwargs = kwargs or {}
    try:
        import threading

        result = []
        error = []

        def worker():
            try:
                r = fn(*args, **kwargs)
                result.append(r)
            except Exception as e:
                error.append(e)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout_sec)
        if t.is_alive():
            print(f"    [TIMEOUT] {fn.__name__} depasse {timeout_sec}s, abandon")
            return []
        if error:
            raise error[0]
        return result[0] if result else []
    except Exception as e:
        print(f"    Erreur {fn.__name__}: {e}")
        return []


def collect_from_web(
    statut: str | None = None, limit: int = 5000, pays: str = "France"
) -> list[dict]:
    global _statut, _pays
    _statut = statut
    _pays = pays
    all_results = []

    french_scrapers = [
        ("123ecoles.com", scrape_123ecoles),
        ("etablissements-scolaires.fr", scrape_etablissements_scolaires),
        ("lesecoles.fr", scrape_lesecoles),
    ]

    enseignement_prive_countries = {"belgique", "suisse"}

    scrapers = list(french_scrapers if pays.lower() == "france" else [])
    if pays.lower() in enseignement_prive_countries:
        scrapers.append(("enseignement-prive.info", scrape_enseignement_prive))
    if pays.lower() == "belgique":
        scrapers.append(("fabert.com", scrape_fabert_be))
    if pays.lower() == "suisse":
        scrapers.append(("swissprivate-schools.ch", scrape_swiss_private_schools))
    if pays.lower() == "tunisie":
        scrapers.append(("ecoleprimaire.tn", scrape_ecoleprimaire_tn))
    if pays.lower() != "france":
        scrapers.append(("DuckDuckGo", scrape_ddg_results))

    for name, scraper_fn in scrapers:
        remaining = limit - len(all_results)
        if remaining <= 0:
            break
        print(f"  Scraping {name}...")
        try:
            results = _run_with_timeout(scraper_fn, args=(remaining,), timeout_sec=60)
            for s in results:
                s["pays"] = pays
                normalized = normalize_prospect(s, pays, s["source"])
                all_results.append(normalized)
            print(f"    -> {len(results)} prospects")
        except Exception as e:
            print(f"    Erreur: {e}")

    print(f"  Enrichissement depuis les pages detail (max 10)...")
    enriched = 0
    for p in all_results[: min(limit, 10)]:
        detail_url = p.get("site_web", "")
        if not detail_url or "web_recherche" in detail_url:
            continue
        info = _run_with_timeout(
            _extract_from_detail, args=(detail_url,), timeout_sec=15
        )
        if not info:
            continue
        for field in ["email", "telephone", "site_web"]:
            if info[field]:
                p[field] = info[field]
                enriched += 1

    if pays.lower() == "france":
        print(f"  (France: skip DDGS enrichment, CSV+API suffisent)")
    else:
        print(f"  Recherche des vrais sites web via DuckDuckGo (max 10)...")
        found_websites = 0
        for p in all_results[: min(limit, 10)]:
            url = p.get("site_web", "")
            if url and not _is_directory_url(url):
                continue
            if url and _is_directory_url(url):
                real = _run_with_timeout(
                    _find_real_website,
                    args=(p.get("nom", ""), p.get("ville", ""), pays),
                    timeout_sec=15,
                )
                if real:
                    p["site_web"] = real
                    found_websites += 1
        if found_websites:
            print(f"    -> {found_websites} vrais sites web trouves")

    if enriched:
        print(f"    -> {enriched} champs enrichis (email/tel/site)")

    print(f"  Total collecte web: {len(all_results)} prospects")
    return all_results[:limit]
