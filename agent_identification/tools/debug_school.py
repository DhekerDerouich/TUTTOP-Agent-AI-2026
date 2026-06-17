import requests, re, warnings
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# Test a single school in detail
url = "https://www.donbosconice.eu"
r = requests.get(url, timeout=8, verify=False, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(r.text, "html.parser")

print(f"=== {url} ({len(r.text)}b) ===")

# 1. Find ALL links
LINK_KW = [
    "equipe",
    "direction",
    "contact",
    "staff",
    "team",
    "ecole",
    "a-propos",
    "apropos",
    "about",
    "notre",
    "l equipe",
    "pedagogique",
    "enseignant",
    "professeur",
]
for a in soup.find_all("a", href=True):
    href = a.get("href", "").lower()
    text = a.get_text(strip=True).lower()
    link_text = a.get_text(strip=True)[:60]
    # Check both href and link text for keywords
    if any(kw in href for kw in LINK_KW) or any(kw in text for kw in LINK_KW):
        print(f'  LINK href={a["href"][:70]} text="{link_text}"')

# 2. Look for any div/section with team-related classes/ids
for tag in soup.find_all(["div", "section", "ul", "nav"]):
    cls = " ".join(tag.get("class", [])).lower()
    tid = tag.get("id", "").lower()
    if any(kw in cls for kw in ["equipe", "team", "staff", "direction", "nav"]):
        print(f'  SECTION class="{cls}" id="{tid}"')
        inner = tag.get_text(strip=True)[:200]
        print(f"    inner: {inner}")

# 3. Print text chunks that have 2+ capitalized words (potential names)
text = soup.get_text(separator=" ", strip=True)
# Look for patterns: Firstname Lastname (2 French words, capitalized)
name_candidates = re.findall(r"\b([A-Z][a-zà-ÿ]{2,})\s+([A-Z][a-zà-ÿ]{2,})\b", text)
print(f"\n  Name candidates (Firstname Lastname): {name_candidates[:20]}")

# Also try: Lastname Firstname (all caps last name)
name_candidates2 = re.findall(
    r"\b([A-Z]{2,}(?:-[A-Z]{2,})?)\s+([A-Z][a-zà-ÿ]+)\b", text
)
print(f"  Name candidates (SURNAME Firstname): {name_candidates2[:15]}")

# Any LinkedIn URLs
linkedins = re.findall(r"linkedin\.com/[a-zA-Z0-9_-]+", text, re.IGNORECASE)
print(f"  LinkedIn URLs: {linkedins}")
