import requests, re, warnings
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

urls_to_check = [
    "https://www.donbosconice.eu/etablissement/",
    "https://giel-don-bosco.org",
    "https://www.don-bosco-gieres.com",
    "https://lepuitsdelaune.fr",
]

for url in urls_to_check:
    try:
        r = requests.get(
            url, timeout=8, verify=False, headers={"User-Agent": "Mozilla/5.0"}
        )
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        print(f"\n=== {url} ({r.status_code}, {len(r.text)}b) ===")

        # Look for name patterns WITHOUT requiring M./Mme prefix
        # Pattern: two capitalized words (basic French name pattern)
        basic_names = re.findall(
            r"\b([A-Z][a-zà-ÿéèêëùüûîïôöç]{2,})\s+([A-Z][a-zà-ÿéèêëùüûîïôöç]{2,})\b",
            text,
        )
        # Filter out common non-name words
        skip = {
            "Don",
            "Bosco",
            "Lycée",
            "Collège",
            "École",
            "Présentation",
            "Projet",
            "Accompagnement",
            "Location",
            "Métiers",
            "Voie",
            "Bac",
            "CAP",
            "BTS",
            "CFA",
            "CFC",
            "Section",
            "International",
            "Contact",
            "Restaurant",
            "Vers",
            "Plus",
            "Tous",
            "Aucun",
            "Titre",
            "Notre",
            "Votre",
            "Cette",
            "Dans",
            "Avec",
            "Entre",
            "Espace",
            "Accès",
            "Accueil",
            "Mots",
            "Suivre",
            "Voir",
            "Nice",
            "Paris",
            "Toulon",
            "Cannes",
            "Grasse",
            "Saint",
        }
        filtered = [(f, l) for f, l in basic_names if f not in skip and l not in skip]
        if filtered:
            print(f"  Basic names: {filtered[:20]}")

        # Look for names near role titles
        role_texts = []
        for kw in [
            "directeur",
            "directrice",
            "responsable",
            "proviseur",
            "principal",
            "chef",
            "président",
            "secrétaire",
            "trésorier",
        ]:
            idx = text.lower().find(kw)
            if idx >= 0:
                chunk = text[max(0, idx - 40) : idx + 80]
                role_texts.append(f"...{chunk}...")
        for rt in role_texts[:5]:
            print(f"  Near role: {rt[:120]}")

        # Look at ALL h2-h4 headings (common for team member names)
        for h in soup.find_all(["h2", "h3", "h4", "h5"]):
            txt = h.get_text(strip=True)
            if txt and len(txt) > 3 and len(txt) < 60:
                # Check if it looks like a name (2 words, capitalized)
                words = txt.split()
                if len(words) >= 2:
                    cap_words = sum(1 for w in words if w[0].isupper() if w)
                    if cap_words >= 2:
                        print(f"  <{h.name}> {txt[:60]}")
    except Exception as e:
        print(f"{url}: {e}")
