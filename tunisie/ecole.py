import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.ecoles.com.tn"
CATEGORIES = [
    {"name": "primaire",    "url": "/etablissements/primaire"},
    {"name": "secondaire",  "url": "/etablissements/secondaire"},
    {"name": "superieur",   "url": "/etablissements/superieur"}
]

def extraire_site_web_depuis_fiche(lien_fiche_complet):
    """Extrait le site web depuis la fiche détail d'un établissement."""
    try:
        response = requests.get(lien_fiche_complet, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Le site web est dans un <li class="site-web"> contenant un <a>
        site_tag = soup.select_one('li.site-web a')
        if site_tag and site_tag.get('href'):
            return site_tag['href'].strip()

        # Fallback : chercher dans .composant_ecoles a
        composant = soup.select_one('.composant_ecoles li.site-web a')
        if composant and composant.get('href'):
            return composant['href'].strip()

        return ""
    except Exception as e:
        print(f"      ⚠️ Erreur fiche ({lien_fiche_complet}): {e}")
        return ""


def extraire_etablissements(categorie):
    print(f"\n🔍 Scraping catégorie : {categorie['name']} ...")
    page = 0
    tous = []

    while True:
        url = BASE_URL + categorie['url'] + f"?page={page}"
        print(f"  📄 Page {page + 1} : {url}")

        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            print(f"  ⚠️ Impossible d'accéder à {url} : {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        boxes = soup.find_all('div', class_='imagebox')

        if not boxes:
            print("  ℹ️ Aucune fiche trouvée, fin de pagination.")
            break

        for box in boxes:
            try:
                # Nom
                nom_tag = box.select_one('.title-content a')
                nom = nom_tag.get_text(strip=True) if nom_tag else ""

                # Type (Primaire / Secondaire / Supérieur) et statut (Privé / Public)
                spans = box.select('.rating span')
                type_etab = spans[0].get_text(strip=True) if len(spans) > 0 else ""
                statut    = spans[1].get_text(strip=True) if len(spans) > 1 else ""

                # Adresse, téléphone, email (dans .box-desc ul li)
                desc_items = box.select('.box-desc ul li')
                adresse    = desc_items[0].select_one('span').get_text(strip=True) if len(desc_items) > 0 else ""
                telephone  = desc_items[1].select_one('span').get_text(strip=True) if len(desc_items) > 1 else ""
                email      = desc_items[2].select_one('span').get_text(strip=True) if len(desc_items) > 2 else ""

                # Ville
                ville_tag = box.select_one('.location .address a')
                ville = ville_tag.get_text(strip=True) if ville_tag else ""

                # Lien vers la fiche détail — peut être relatif OU absolu selon le HTML
                lien_tag  = box.select_one('.location .detail a')
                lien_fiche_raw = lien_tag['href'] if lien_tag and lien_tag.get('href') else ""

                # Construire l'URL complète sans double-préfixe
                if lien_fiche_raw.startswith('http'):
                    lien_fiche_complet = lien_fiche_raw
                elif lien_fiche_raw:
                    lien_fiche_complet = BASE_URL + lien_fiche_raw
                else:
                    lien_fiche_complet = ""

                # Récupérer le site web depuis la fiche détail
                site_web = ""
                if lien_fiche_complet:
                    site_web = extraire_site_web_depuis_fiche(lien_fiche_complet)
                    time.sleep(0.4)   # pause polie pour ne pas surcharger le serveur

                label = nom[:45] if nom else "(sans nom)"
                print(f"    ✓ {label:<45} → {site_web if site_web else '(pas de site web)'}")

                tous.append({
                    "categorie":  categorie['name'],
                    "nom":        nom,
                    "type":       type_etab,
                    "statut":     statut,
                    "adresse":    adresse,
                    "ville":      ville,
                    "telephone":  telephone,
                    "email":      email,
                    "site_web":   site_web,
                    "lien_fiche": lien_fiche_complet
                })

            except Exception as e:
                print(f"    ⚠️ Erreur sur une fiche : {e}")

        # Pagination
        next_btn = soup.select_one('.pager__item--next a')
        if not next_btn:
            print("  ✅ Dernière page atteinte.")
            break

        page += 1
        time.sleep(1)

    return tous


# ── Lancement ──────────────────────────────────────────────────────────────────
tous = []
for cat in CATEGORIES:
    tous.extend(extraire_etablissements(cat))

df = pd.DataFrame(tous)
df.to_csv('tous_etablissements_avec_sites_web.csv', index=False, encoding='utf-8-sig')
print(f"\n✅ Terminé ! {len(df)} établissements extraits → tous_etablissements_avec_sites_web.csv")