"""Debug: test extraction on one school with detailed output."""

import sys, re, warnings

sys.path.insert(0, r"C:\Users\dheke\Desktop\TUT'TOP\agent_identification")
warnings.filterwarnings("ignore")

from tools.contact_collector import (
    _scrape_school,
    _page_type,
    _extract_from_cards,
    _extract_from_text,
)
from bs4 import BeautifulSoup
import requests

BASE = "https://giel-don-bosco.org"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
session = requests.Session()
session.verify = False

# Get homepage
r = session.get(BASE, headers=HEADERS, timeout=8)
home = r.text
soup_home = BeautifulSoup(home, "html.parser")
text = soup_home.get_text(separator=" ", strip=True)

print(f"=== Homepage ({BASE}) === ")
print(f"Page type: {_page_type(BASE, soup_home)}")
print(f"Text length: {len(text)}")

# Check for M. pattern
for m in re.finditer(
    r"(?:M\.|Mme|Ms|Mr|Monsieur|Madame|M\.me)\s+([A-Za-z\xc0-\xff]+(?:[\s-][A-Za-z\xc0-\xff]+){0,2})",
    text,
):
    print(f"  Found prefix name: '{m.group(1).strip()}' at pos {m.start()}")

# Check for all-caps near role
for m in re.finditer(r"\b([A-Z\xc0-\xdf]{3,}(?:-[A-Z\xc0-\xdf]{3,})?)\b", text):
    word = m.group(1)
    pos = m.start()
    start = max(0, pos - 40)
    end = min(len(text), pos + len(word) + 40)
    ctx = text[start:end]
    for kw in [
        "directeur",
        "directrice",
        "proviseur",
        "principal",
        "chef",
        "responsable",
    ]:
        if kw in ctx.lower():
            print(f"  All-caps near role: '{word}' ctx='...{ctx}...'")
            break

# Check TEAM_PATHS via HEAD
team_paths = [
    "/equipe-pedagogique",
    "/organigramme",
    "/direction",
    "/notre-equipe",
    "/equipe",
    "/presentation",
    "/mot-du-directeur",
    "/contact",
    "/ecole",
    "/lequipe",
    "/corps-enseignant",
    "/enseignants",
    "/gouvernance",
]
for path in team_paths:
    url = f"https://giel-don-bosco.org{path}"
    try:
        hr = session.head(url, headers=HEADERS, timeout=3)
        print(f"  HEAD {path:30s} -> {hr.status_code}")
    except Exception as e:
        print(f"  HEAD {path:30s} -> ERR {str(e)[:30]}")

# Now try the full scrape
print("\n=== Full scrape ===")
info = _scrape_school("giel-don-bosco.org", BASE, session, HEADERS, 5)
print(f"Names: {info['names']}")
print(f"LinkedIn: {info['linkedins']}")
print(f"Emails: {info['emails']}")
