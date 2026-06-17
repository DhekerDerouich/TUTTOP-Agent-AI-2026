import requests, re, warnings
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

sites = [
    "https://www.donbosconice.eu",
    "https://giel-don-bosco.org",
    "https://www.don-bosco-gieres.com",
    "https://ermitage.fr",
    "https://lepuitsdelaune.fr",
]
for url in sites:
    try:
        r = requests.get(
            url, timeout=8, verify=False, headers={"User-Agent": "Mozilla/5.0"}
        )
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        lines = [l.strip() for l in text.split() if l.strip()]
        print(f"=== {url} ({len(r.text)}b) ===")
        m = re.findall(
            r"(?:M\.|Mme|Ms|Mr|Monsieur|Madame)\s+([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)+)",
            text,
        )
        print(f"  M./Mme pattern: {m}")
        for kw in [
            "directeur",
            "directrice",
            "responsable",
            "proviseur",
            "principal",
            "chef",
        ]:
            ctx = [
                lines[i] for i in range(min(20, len(lines))) if kw in lines[i].lower()
            ]
            if ctx:
                print(f'  Near "{kw}": {ctx[:3]}')
        h_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
        for h in h_tags[:15]:
            txt = h.get_text(strip=True)
            if txt and len(txt) > 3 and any(c.isupper() for c in txt):
                print(f"  <{h.name}>{txt[:80]}</{h.name}>")
        print()
    except Exception as e:
        print(f"{url}: {e}\n")
