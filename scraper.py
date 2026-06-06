import requests
import ssl
from bs4 import BeautifulSoup
import pandas as pd
import time

ssl._create_default_https_context = ssl._create_unverified_context

# Liste des URLs (tu devras l’enrichir avec de vraies écoles)
urls = [
    "https://www.esprit.tn",
    "https://www.supcom.tn",
    "https://www.insat.rnu.tn",
    "https://www.eniso.rnu.tn"
]

def determiner_type(url):
    if ".rnu.tn" in url or ".gov.tn" in url:
        return "Public"
    else:
        return "Privé"  # À affiner plus tard

def extraire_nom(url, soup):
    # Essayer d’abord la balise title
    if soup.title and soup.title.string:
        nom = soup.title.string.strip()
        # Nettoyer : enlever "École d’ingénieurs..." si trop long
        if len(nom) > 50:
            nom = nom[:50]
        return nom
    # Sinon, prendre le nom depuis l’URL
    return url.replace("https://www.", "").replace(".tn", "").replace(".com", "")

def analyser_ecole(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Nom
        nom = extraire_nom(url, soup)
        
        # 2. Type
        type_etab = determiner_type(url)
        
        # 3. Localisation (pour l’instant, on met "Non trouvée" – à améliorer)
        localisation = "Non trouvée"
        
        # 4. Site web (on a déjà l’URL)
        
        return {
            "nom": nom,
            "localisation": localisation,
            "type": type_etab,
            "site_web": url,
            "statut": "succès"
        }
    
    except Exception as e:
        return {
            "nom": "Erreur",
            "localisation": "Erreur",
            "type": "Erreur",
            "site_web": url,
            "statut": str(e)[:100]
        }

# Scraping
resultats = []
for url in urls:
    print(f"Analyse de {url}...")
    resultats.append(analyser_ecole(url))
    time.sleep(1)

# Sauvegarde
df = pd.DataFrame(resultats)
df.to_csv('prospects_mission_5_1.csv', index=False, encoding='utf-8-sig')

print("\n✅ Mission 5.1 terminée ! Fichier 'prospects_mission_5_1.csv' créé.")