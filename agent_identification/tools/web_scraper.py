import ssl
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional


ssl._create_default_https_context = ssl._create_unverified_context

REQUEST_TIMEOUT = 15
RATE_LIMIT_DELAY = 1.0


def fetch_website(url: str) -> str:
    """Télécharge le contenu HTML d'un site web d'école."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.split("\n") if len(l) > 30]
        return "\n".join(lines[:200])
    except Exception as e:
        return f"Erreur de chargement: {e}"


def search_schools_on_page(url: str) -> list[dict]:
    """Extrait la liste des établissements depuis une page d'annuaire."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        schools = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if (
                text
                and len(text) > 5
                and (
                    "ecole" in href.lower()
                    or "school" in href.lower()
                    or "etablissement" in href.lower()
                )
            ):
                schools.append(
                    {
                        "nom": text,
                        "url": href if href.startswith("http") else url + href,
                    }
                )

        time.sleep(RATE_LIMIT_DELAY)
        return schools[:50]
    except Exception as e:
        return [{"error": str(e)}]
