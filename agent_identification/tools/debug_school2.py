import requests, re, warnings
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

url = "https://www.donbosconice.eu"
r = requests.get(url, timeout=8, verify=False, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(r.text, "html.parser")

# Find ALL links on the page, not just visible ones
all_links = []
for a in soup.find_all("a", href=True):
    href = a.get("href", "")
    text = a.get_text(strip=True)[:50]
    all_links.append((href, text))

print(f"=== ALL links on {url} ===")
for href, text in all_links:
    print(f'  {href[:80]:80s} "{text}"')

# Now try some common team page paths directly
print("\n=== Testing known paths ===")
paths = [
    "/equipe-pedagogique",
    "/equipe",
    "/direction",
    "/notre-equipe",
    "/organigramme",
    "/l-equipe",
    "/lequipe",
    "/staff",
    "/contact",
    "/ecole",
    "/presentation",
    "/notre-projet",
]
for path in paths:
    try:
        pu = url + path
        pr = requests.get(
            pu, timeout=5, verify=False, headers={"User-Agent": "Mozilla/5.0"}
        )
        print(f"  {path:30s} -> {pr.status_code} ({len(pr.text)}b)")
    except Exception as e:
        print(f"  {path:30s} -> ERR {e}")
