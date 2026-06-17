import os
import re
import time
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"

SCHOOL_TEAM_PATHS = [
    "/equipe-pedagogique",
    "/equipe",
    "/direction",
    "/contact",
    "/notre-equipe",
    "/lequipe",
    "/staff",
    "/a-propos",
    "/qui-sommes-nous",
    "/presentation",
    "/ecole",
    "/equipe-educative",
    "/corps-enseignant",
    "/enseignants",
    "/notre-projet",
    "/l-equipe",
    "/l-equipe-pedagogique",
    "/gouvernance",
    "/organisation",
]


def export_chauds_for_n8n(
    input_csv: str = "data/all_data_enriched.csv",
    output_csv: str = "data/prospects_chauds.csv",
    max_schools: int = 500,
    private_only: bool = True,
):
    """Exporte les prospects Chauds vers un CSV propre pour n8n.

    Par defaut: 500 ecoles privees max (temps d'execution n8n raisonnable).
    Met private_only=False pour exporter tous les Chauds (public inclus).
    """
    in_path = Path(__file__).parent.parent / input_csv

    df = pd.read_csv(in_path, dtype=str).fillna("")
    chauds = df[df["qualification"] == "Chaud"].copy()

    def extract_domain(site):
        if not site or site == "nan":
            return ""
        s = str(site).strip()
        if not s.startswith("http"):
            s = "https://" + s
        try:
            d = urlparse(s).netloc.lower()
            if d.startswith("www."):
                d = d[4:]
            return d
        except:
            return ""

    chauds["domaine"] = chauds["site_web"].apply(extract_domain)

    generic = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "laposte.net",
        "free.fr",
        "orange.fr",
        "wanadoo.fr",
        "sfr.fr",
    }
    chauds = chauds[~chauds["domaine"].isin(generic)]
    chauds = chauds[chauds["domaine"] != ""]

    # Filtrer les domaines academiques (ac-*.fr) — pas de pages equipe
    academic = chauds["domaine"].str.contains(r"ac-[a-z-]+\.fr$", regex=True, na=False)
    if private_only:
        chauds = chauds[~academic]
        chauds = chauds[chauds["type"] == "Privé"]

    # Trier par score (meilleurs d'abord) et limiter
    chauds["score_num"] = pd.to_numeric(chauds["score"], errors="coerce").fillna(0)
    chauds = chauds.sort_values("score_num", ascending=False)
    chauds = chauds.drop(columns=["score_num"])

    # Deduplicater par domaine (garder le meilleur score)
    chauds = chauds.drop_duplicates(subset=["domaine"], keep="first")
    chauds = chauds.head(max_schools)

    export_cols = [
        "nom",
        "type",
        "domaine",
        "site_web",
        "pays",
        "localisation",
        "score",
    ]
    chauds = chauds[export_cols]

    out_path = Path(__file__).parent.parent / output_csv
    chauds.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Exporte {len(chauds)} prospects Chauds -> {out_path}")
    print(f"  Domaines uniques: {chauds['domaine'].nunique()}")
    return out_path


def import_contacts_from_n8n(
    contacts_csv: str = "data/contacts.csv",
    output_csv: str = "data/all_data_enriched.csv",
):
    """Relit le fichier contacts.csv genere par n8n et le fusionne.

    Le CSV n8n doit avoir les colonnes:
      domaine, contact_nom, contact_titre, linkedin_url, source
    """
    contacts_path = Path(__file__).parent.parent / contacts_csv
    if not contacts_path.exists():
        print(f"[ERR] Fichier contacts introuvable: {contacts_path}")
        return

    df_contacts = pd.read_csv(contacts_path, dtype=str).fillna("")
    print(f"Contacts importes depuis n8n: {len(df_contacts)}")

    if "domaine" not in df_contacts.columns:
        print("[ERR] Colonne 'domaine' requise dans le CSV contacts")
        return

    # Compter les contacts par domaine
    contact_counts = (
        df_contacts.groupby("domaine")
        .agg(
            nb_contacts=("contact_nom", "count"),
            contacts_list=("contact_nom", lambda x: " | ".join(x)),
            titres_list=("contact_titre", lambda x: " | ".join(x)),
            linkedin_list=(
                "linkedin_url",
                lambda x: " | ".join(str(v) for v in x if v),
            ),
        )
        .reset_index()
    )

    # Charger les donnees enrichies
    enriched_path = Path(__file__).parent.parent / output_csv
    df = pd.read_csv(enriched_path, dtype=str).fillna("")

    # Extraire le domaine pour la jointure
    def extract_domain(site):
        if not site or site == "nan":
            return ""
        s = str(site).strip()
        if not s.startswith("http"):
            s = "https://" + s
        try:
            d = urlparse(s).netloc.lower()
            if d.startswith("www."):
                d = d[4:]
            return d
        except:
            return ""

    df["domaine"] = df["site_web"].apply(extract_domain)

    # Ajouter les colonnes contacts
    df = df.merge(contact_counts, on="domaine", how="left")
    df["nb_contacts"] = df["nb_contacts"].fillna(0).astype(int)
    df["contacts_list"] = df["contacts_list"].fillna("")
    df["titres_list"] = df["titres_list"].fillna("")
    df["linkedin_list"] = df["linkedin_list"].fillna("")

    # Nettoyer colonne domaine temporaire
    df = df.drop(columns=["domaine"])

    out_path = Path(__file__).parent.parent / output_csv
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Fusionne: {len(df)} prospects enrichis avec contacts")
    print(f"  Prospects avec contacts: {(df['nb_contacts'] > 0).sum()}")
    print(f"  Contacts total: {df['nb_contacts'].sum()}")
    print(f"  -> {out_path}")


def hunter_find_email(domain: str, first_name: str = "", last_name: str = "") -> dict:
    """Cherche un email via Hunter.io pour un domaine + nom.

    Retourne: {"email": "...", "score": 0-100, "sources": [...]}
    Gratuit: 25 requetes/mois.
    """
    key = os.getenv("HUNTER_API_KEY", "")
    if not key:
        return {"email": "", "score": 0}

    params = {"domain": domain, "api_key": key}
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params=params,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return {
                "email": data.get("email", ""),
                "score": data.get("score", 0),
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
            }
        elif resp.status_code == 429:
            print("  [Hunter] Rate limit atteint")
        else:
            err = resp.json().get("errors", [{}])[0].get("details", resp.text[:100])
            if "404" not in str(resp.status_code):
                print(f"  [Hunter] Err {resp.status_code}: {err}")
    except Exception as e:
        print(f"  [Hunter] Exception: {e}")

    return {"email": "", "score": 0}


def hunter_enrich_contacts(
    input_csv: str = "data/contacts.csv",
    output_csv: str = "data/contacts.csv",
    max_requests: int = 25,
):
    """Enrichit le fichier contacts.csv avec les emails via Hunter.io.

    Gratuit: 25 requetes/mois. Utilise-les sur les meilleurs contacts.
    Consomme 1 requete par contact avec nom complet trouve.
    """
    in_path = Path(__file__).parent.parent / input_csv
    if not in_path.exists():
        print(f"[ERR] Fichier introuvable: {in_path}")
        return

    df = pd.read_csv(in_path, dtype=str).fillna("")

    if "email" not in df.columns:
        df["email"] = ""

    candidates = df[
        (df["contact_nom"] != "") & ((df["email"].isna()) | (df["email"] == ""))
    ].copy()

    if len(candidates) == 0:
        print("Aucun contact a enrichir (deja tous emails ou pas de noms)")
        return

    print(f"Enrichissement Hunter: {min(max_requests, len(candidates))} requetes")
    used = 0

    for idx, row in candidates.iterrows():
        if used >= max_requests:
            break

        nom = row["contact_nom"]
        parts = nom.strip().split()
        if len(parts) < 2:
            continue

        last_name = parts[0]
        first_name = " ".join(parts[1:])

        domaine = row.get("domaine", "")
        if not domaine:
            continue

        result = hunter_find_email(domaine, first_name, last_name)
        used += 1

        if result["email"]:
            df.at[idx, "email"] = result["email"]
            print(
                f"  [{used}/{max_requests}] {nom:30s} -> {result['email']} (score: {result['score']})"
            )
        else:
            print(f"  [{used}/{max_requests}] {nom:30s} -> pas d'email trouve")

        time.sleep(1)

    out_path = Path(__file__).parent.parent / output_csv
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(
        f"\nFini. {used} requetes utilisees. Emails trouves: {(df['email'] != '').sum()}"
    )


def _make_absolute(base_url: str, link: str) -> str:
    """Convertit un lien relatif en absolu."""
    if link.startswith("http"):
        return link
    if link.startswith("/"):
        return base_url + link
    return base_url + "/" + link


# Mots à exclure des candidats noms (majuscules courantes non-nominatives)
_SKIP_WORDS = {
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
    "Restauration",
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
    "Infos",
    "Actualités",
    "Inscription",
    "Offres",
    "Emploi",
    "Tarifs",
    "Horaires",
    "Calendrier",
    "Vie",
    "Saint",
    "Note",
    "Sujet",
    "Partager",
    "Facebook",
    "Twitter",
    "Linkedin",
    "Instagram",
    "YouTube",
    "Tiktok",
    "Newsletter",
    "Mentions",
    "Légales",
    "Crédits",
    "Plan",
    "Site",
    "Rechercher",
    "Connexion",
    "Déconnexion",
    "Soumettre",
    "Adresse",
    "Téléphone",
    "Fax",
    "Email",
    "Siret",
    "RNA",
    "RCS",
    "Directeur",
    "Directrice",
    "Responsable",
    "Chef",
    "Proviseur",
    "Principal",
    "Président",
    "Secrétaire",
    "Trésorier",
    "Comptable",
    "Professeur",
    "Enseignant",
    "Formateur",
    "Éducateur",
    "Animateur",
    "DIRECTEUR",
    "DIRECTRICE",
    "RESPONSABLE",
    "PROVISEUR",
    "PRINCIPAL",
    "PRÉSIDENT",
    "PRÉSIDENTE",
    "SECRÉTAIRE",
    "TRÉSORIER",
    "COMPTABLE",
    "Apprentissage",
    "Formation",
    "Pédagogique",
    "Éducatif",
    "Pastorale",
    "Anglais",
    "Allemand",
    "Espagnol",
    "Italien",
    "Histoire",
    "Géographie",
    "Mathématiques",
    "Sciences",
    "Physique",
    "Chimie",
    "SVT",
    "EPS",
    "Musique",
    "Arts",
    "Plastiques",
    "Théâtre",
    "Cinéma",
    "Atelier",
    "Bibliothèque",
    "CDI",
    "Informatique",
    "Technologie",
    "DPEGE",
    "Enseignement",
    "Catholique",
    "Privé",
    "Public",
    "Établissement",
    "France",
    "Paris",
    "Lyon",
    "Marseille",
    "Nice",
    "Toulon",
    "Cannes",
    "Grasse",
    "Antibes",
    "Aix",
    "Bordeaux",
    "Toulouse",
    "Lille",
    "Strasbourg",
    "Nantes",
    "Rennes",
    "Grenoble",
    "Montpellier",
    "Clermont",
    "Limoges",
    "Dijon",
    "Orléans",
    "Tours",
    "Rouen",
    "Caen",
    "Amiens",
    "Reims",
    "Nancy",
    "Metz",
    "Besançon",
    "Poitiers",
    "La",
    "Le",
    "Les",
    "Des",
    "Du",
    "De",
    "Sur",
    "Sous",
    "Dans",
    "Objectifs",
    "Dominante",
    "Objectif",
    "Pastorale",
    "Livret",
    "Règlement",
    "Dispositif",
    "Modalités",
    "Pédagogiques",
    "Informations",
    "Candidature",
    "Résultat",
    "Résultats",
    "Parcours",
    "Matières",
    "Option",
    "Options",
    "Atelier",
    "Travaux",
    "Tutorat",
}


def _is_name_candidate(text: str, min_words: int = 1) -> bool:
    """Vérifie si un texte ressemble à un nom propre."""
    words = text.split()
    if len(words) < min_words or len(words) > 5:
        return False
    for w in words:
        if not re.match(r"^[A-ZÀ-Ÿ][a-zà-ÿéèêëùüûîïôöç'\-]+$", w) and not re.match(
            r"^[A-ZÀ-Ÿ]{2,}(?:-[A-ZÀ-Ÿ]{2,})?$", w
        ):
            return False
    # Vérification insensible à la casse contre les mots exclus
    w_upper = [w.upper() for w in words]
    skip_upper = {w.upper() for w in _SKIP_WORDS}
    # Si un seul mot: rejeter si c'est un mot exclu
    if len(words) == 1:
        if w_upper[0] in skip_upper:
            return False
    # Si plusieurs mots: rejeter si l'un des mots supplémentaires est exclu
    else:
        if any(w in skip_upper for w in w_upper[1:]):
            return False
    return True


def _looks_like_surname(word: str) -> bool:
    """Vérifie si un mot MAJUSCULES ressemble à un patronyme (vs mot quelconque)."""
    if len(word) < 3 or len(word) > 15:
        return False
    # Doit contenir au moins 2 voyelles (patronyme français)
    vowels = sum(1 for c in word if c in "AEIOUYÀÉÈÊËÎÏÔÖÛÙaeiouyàéèêëîïôöûù")
    if vowels < 2:
        return False
    # Ne doit pas être un mot français courant
    common = {
        "DIRECTEUR",
        "DIRECTRICE",
        "RESPONSABLE",
        "CONTACT",
        "ACCUEIL",
        "INSCRIPTION",
        "FORMATION",
        "ENSEIGNANT",
        "PROFESSEUR",
        "HORAIRES",
        "TARIFS",
        "MENTIONS",
        "LEGALES",
        "NEWSLETTER",
        "FACEBOOK",
        "TWITTER",
        "INSTAGRAM",
        "YOUTUBE",
        "LINKEDIN",
        "EQUIPE",
        "DIRECTION",
        "PRESENTATION",
        "ORGANIGRAMME",
        "GOUVERNANCE",
        "ETABLISSEMENT",
        "COLLEGE",
        "LYCEE",
        "ECOLE",
        "PRIVE",
        "PUBLIC",
        "CATHOLIQUE",
        "ENSEIGNEMENT",
        "FORMATION",
        "APPRENTISSAGE",
        "PROJET",
        "PEDAGOGIQUE",
        "EDUCATIF",
        "BIENVENUE",
        "INFOS",
        "ACTUALITES",
        "CONTACTEZ",
        "IDISS",
        "APEL",
        "OGEC",
        "UFA",
        "AESH",
        "CFA",
        "CFC",
        "BOUTIQUE",
        "UNIFORME",
        "PRONOTE",
        "ENT",
        "CDI",
        "OBJECTIFS",
        "PASTORALE",
        "LIVRET",
        "PRÉSENTATION",
        "PRESENTATION",
        "ÉTABLISSEMENT",
        "ETABLISSEMENT",
        "ÉDUCATIF",
        "EDUCATIF",
        "PÉDAGOGIQUE",
        "PEDAGOGIQUE",
        "ÉLÈVES",
        "ELEVES",
        "INSCRIPTIONS",
        "ACTUALITÉS",
        "NEWSLETTER",
        "MENTIONS",
        "LÉGALES",
        "LEGALES",
        "COORDONNÉES",
        "COORDONNEES",
        "FONCTIONNEMENT",
        "RENSEIGNEMENTS",
        "CONDITIONS",
        "PARTENAIRES",
        "HÉBERGEMENT",
        "RESTAURATION",
        "TARIFS SCOLAIRES",
        "CALENDRIER",
        "NOTICE",
        "JAVASCRIPT",
        "EPI",
    }
    if word in common:
        return False
    return True


def _is_near_role(word: str, text: str, pos: int, window: int = 35) -> str:
    """Vérifie si un mot est près d'un rôle décisionnaire. Retourne le rôle."""
    decision_roles = [
        "directeur",
        "directrice",
        "proviseur",
        "principal",
        "chef",
        "responsable",
        "président",
        "présidente",
        "coordinateur",
        "coordinatrice",
    ]
    start = max(0, pos - window)
    end = min(len(text), pos + len(word) + window)
    context = text[start:end].lower()
    for role in decision_roles:
        if role in context:
            return role.capitalize()
    return ""


def _extract_role_after(name_end: int, text: str, max_len: int = 60) -> str:
    """Extrait le rôle qui suit un nom dans le texte."""
    chunk = text[name_end : name_end + max_len].strip()
    if "@" in chunk:
        chunk = chunk[: chunk.index("@")]
    # Ignorer si ça commence par un numéro de téléphone
    if re.match(r"^0\d[\s\d]+", chunk):
        return ""
    # Arrêter au premier séparateur de phrase
    for sep in [",", ". ", "! ", "? ", "|", "\n"]:
        idx = chunk.find(sep)
        if idx > 0:
            chunk = chunk[:idx]
    result = chunk.strip(" ,;:\t-")
    # Ignorer si le résultat ressemble à du JS ou du contenu technique
    if len(result) > 50 or "JavaScript" in result:
        return ""
    return result[:40]


def _page_type(url: str, soup) -> str:
    """Détermine le type de page: home / team / contact / other."""
    path = urlparse(url).path.lower().rstrip("/")
    if not path or path == "" or path == "/":
        return "home"
    team_kw = [
        "equipe",
        "direction",
        "organigramme",
        "staff",
        "team",
        "membre",
        "gouvernance",
        "dirigeant",
        "mot-du-directeur",
        "mot-de-la-directrice",
        "corps-enseignant",
        "enseignant",
        "presentation",
        "notre-equipe",
        "lequipe",
        "l-equipe",
        "equipe-educative",
        "pedagogique",
    ]
    if any(kw in path for kw in team_kw):
        return "team"
    if "contact" in path:
        return "contact"
    # Vérifier le titre H1 de la page
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(strip=True).lower()
        if any(kw in h1_text for kw in ["équipe", "direction", "organigramme"]):
            return "team"
    return "other"


def _extract_from_cards(soup, names_dict, linkedins, emails):
    """Extrait les noms/rôles depuis les cartes membres structurées (Divi, etc.)."""
    card_selectors = [
        re.compile(
            r"(?:team|equipe|membre|member|person)[-_]?(?:member|item|card)?", re.I
        ),
        re.compile(r"et_pb_team_member", re.I),
        re.compile(r"fusion-person", re.I),
        re.compile(r"et_pb_member", re.I),
    ]
    for selector in card_selectors:
        for container in soup.find_all(
            ["div", "section", "li", "article", "aside"], class_=selector
        ):
            name_tag = container.find(
                ["h3", "h4", "h5", "strong", "b", "span", "p", "div"]
            )
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name or not _is_name_candidate(name):
                continue
            role_tag = container.find(
                ["p", "span", "div", "em", "small"],
                class_=re.compile(r"(role|position|titre|fonction|job|title)", re.I),
            )
            role = role_tag.get_text(strip=True) if role_tag else ""
            if name not in names_dict:
                names_dict[name] = role
            for a in container.find_all("a", href=True):
                href = a["href"]
                if "linkedin.com" in href.lower():
                    linkedins.add(href)
                if href.startswith("mailto:"):
                    emails.add(href[7:])
    return names_dict


def _extract_from_text(soup, text, names_dict, linkedins):
    """Extraction textuelle (uniquement stratégies haute précision)."""
    # Stratégie A: Préfixe + Nom(s)
    for m in re.finditer(
        r"(?:M\.|Mme|Ms|Mr|Monsieur|Madame|M\.me)\s+"
        r"([A-Za-zÀ-ÿ]+(?:[\s-][A-Za-zÀ-ÿ]+){0,1})",
        text,
    ):
        name = m.group(1).strip()
        if not _is_name_candidate(name):
            continue
        role = _extract_role_after(m.end(), text)
        if name not in names_dict:
            names_dict[name] = role

    # Stratégie B: Patronyme MAJUSCULES près d'un rôle décisionnaire
    for m in re.finditer(r"\b([A-ZÀ-Ÿ]{3,}(?:-[A-ZÀ-Ÿ]{3,})?)\b", text):
        word = m.group(1)
        if not _looks_like_surname(word):
            continue
        pos = m.start()
        role = _is_near_role(word, text, pos)
        if role and word not in names_dict:
            names_dict[word] = role

    return names_dict


def _scrape_school(domaine: str, base_url: str, session, headers, timeout) -> dict:
    """Scrape une école et retourne {noms_dict, linkedins, emails}."""
    from bs4 import BeautifulSoup

    result = {"names": {}, "linkedins": set(), "emails": set()}

    # -- Étape 1: Page d'accueil --
    home_html = None
    try:
        r = session.get(base_url, headers=headers, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 200:
            home_html = r.text
    except Exception:
        pass
    if not home_html:
        return result

    soup_home = BeautifulSoup(home_html, "html.parser")
    home_text = soup_home.get_text(separator=" ", strip=True)

    # Collecter LinkedIn + email depuis la homepage
    for m in re.finditer(r"linkedin\.com/[a-zA-Z0-9_-]+", home_text, re.I):
        result["linkedins"].add(f"https://{m.group(0).lower()}")
    for a in soup_home.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            result["emails"].add(href[7:])

    # -- Étape 2: Trouver les pages équipe --
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
        "pedagogique",
        "enseignant",
        "professeur",
        "organigramme",
        "presentation",
        "gouvernance",
    ]
    team_urls = set()
    for a in soup_home.find_all("a", href=True):
        href = a.get("href", "").lower()
        text = a.get_text(strip=True).lower()
        if any(kw in href for kw in LINK_KW) or any(kw in text for kw in LINK_KW):
            team_urls.add(_make_absolute(base_url, a["href"]))

    # Essayer les chemins directs par priorité
    TEAM_PATHS = [
        "/equipe-pedagogique",
        "/organigramme",
        "/direction",
        "/notre-equipe",
        "/equipe",
        "/lequipe-pedagogique",
        "/lequipe",
        "/l-equipe",
        "/presentation",
        "/mot-du-directeur",
        "/mot-de-la-directrice",
        "/corps-enseignant",
        "/enseignants",
        "/equipe-educative",
        "/nos-equipes",
        "/gouvernance",
        "/organisation",
        "/dirigeants",
        "/membres",
        "/staff",
        "/contact",
        "/a-propos",
        "/qui-sommes-nous",
        "/ecole",
        "/notre-ecole",
        "/notre-projet",
        "/presentation-de-lequipe",
        "/notre-organisation",
        "/about",
        "/lecole",
    ]
    MAX_TEAM = 3
    if len(team_urls) < MAX_TEAM:
        for path in TEAM_PATHS:
            if len(team_urls) >= MAX_TEAM:
                break
            full_url = _make_absolute(base_url, path)
            if full_url in team_urls:
                continue
            try:
                hr = session.head(full_url, headers=headers, timeout=3)
                if hr.status_code == 200:
                    team_urls.add(full_url)
            except Exception:
                continue

    # -- Étape 3: Télécharger + extraire les pages équipe (URL + html) --
    pages_to_scrape = [(base_url, home_html)]
    for tu in list(team_urls)[:MAX_TEAM]:
        try:
            r = session.get(tu, headers=headers, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 200:
                pages_to_scrape.append((tu, r.text))
        except Exception:
            continue

    for page_url, html in pages_to_scrape:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        page_type = _page_type(page_url, soup)

        # LinkedIn + email sur toutes les pages
        for m in re.finditer(r"linkedin\.com/[a-zA-Z0-9_-]+", text, re.I):
            result["linkedins"].add(f"https://{m.group(0).lower()}")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                result["emails"].add(a["href"][7:])

        # Noms: extraction textuelle haute précision + cartes sur toutes les pages
        _extract_from_text(soup, text, result["names"], result["linkedins"])
        _extract_from_cards(
            soup, result["names"], result["linkedins"], result["emails"]
        )

    return result

    # -- Étape 2: Trouver les pages équipe --
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
        "pedagogique",
        "enseignant",
        "professeur",
        "organigramme",
        "presentation",
        "gouvernance",
    ]
    team_urls = set()
    for a in soup_home.find_all("a", href=True):
        href = a.get("href", "").lower()
        text = a.get_text(strip=True).lower()
        if any(kw in href for kw in LINK_KW) or any(kw in text for kw in LINK_KW):
            team_urls.add(_make_absolute(base_url, a["href"]))

    # Essayer les chemins directs par priorité
    TEAM_PATHS = [
        "/equipe-pedagogique",
        "/organigramme",
        "/direction",
        "/notre-equipe",
        "/equipe",
        "/lequipe-pedagogique",
        "/lequipe",
        "/l-equipe",
        "/presentation",
        "/mot-du-directeur",
        "/mot-de-la-directrice",
        "/corps-enseignant",
        "/enseignants",
        "/equipe-educative",
        "/nos-equipes",
        "/gouvernance",
        "/organisation",
        "/dirigeants",
        "/membres",
        "/staff",
        "/contact",
        "/a-propos",
        "/qui-sommes-nous",
        "/ecole",
        "/notre-ecole",
        "/notre-projet",
        "/presentation-de-lequipe",
        "/notre-organisation",
        "/about",
        "/lecole",
    ]
    MAX_TEAM = 3
    if len(team_urls) < MAX_TEAM:
        for path in TEAM_PATHS:
            if len(team_urls) >= MAX_TEAM:
                break
            full_url = _make_absolute(base_url, path)
            if full_url in team_urls:
                continue
            try:
                hr = session.head(full_url, headers=headers, timeout=3)
                if hr.status_code == 200:
                    team_urls.add(full_url)
            except Exception:
                continue

    # -- Étape 3: Télécharger + extraire les pages équipe --
    pages_to_scrape = [home_html]
    for tu in list(team_urls)[:MAX_TEAM]:
        try:
            r = session.get(tu, headers=headers, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 200:
                pages_to_scrape.append(r.text)
        except Exception:
            continue

    for html in pages_to_scrape:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        page_url = base_url  # approximate, used for page_type
        page_type = _page_type(base_url, soup)

        # LinkedIn + email sur toutes les pages
        for m in re.finditer(r"linkedin\.com/[a-zA-Z0-9_-]+", text, re.I):
            result["linkedins"].add(f"https://{m.group(0).lower()}")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                result["emails"].add(a["href"][7:])

        # Noms : seulement sur les pages de type team
        if page_type == "team":
            _extract_from_cards(
                soup, result["names"], result["linkedins"], result["emails"]
            )
            _extract_from_text(soup, text, result["names"], result["linkedins"])
        # Sur la page d'accueil, extraction limitée (cartes uniquement)
        elif page_type == "home":
            _extract_from_cards(
                soup, result["names"], result["linkedins"], result["emails"]
            )

    return result


def run_direct_scrape(
    input_csv: str = "data/prospects_chauds.csv",
    output_csv: str = "data/contacts.csv",
    max_schools: int = 200,
):
    """Scrape les écoles privées « Chaud » pour trouver contacts décisionnaires.

    Méthode:
      1. Page d'accueil → LinkedIn + emails + navigation vers pages équipe
      2. Pages équipe (détectées via nav ou chemins directs) → extraction
         structurée des noms + rôles
      3. Extraction haute précision: cartes membres (Divi, etc.), préfixe
         M./Mme, patronymes MAJUSCULES près d'un rôle décisionnaire
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    adapter = HTTPAdapter(max_retries=Retry(total=0))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.verify = False
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    TIMEOUT = 5

    in_path = Path(__file__).parent.parent / input_csv
    if not in_path.exists():
        print(f"[ERR] Fichier introuvable: {in_path}")
        print("  Lance d'abord: export_chauds_for_n8n()")
        return

    df = pd.read_csv(in_path, dtype=str).fillna("")
    df = df[df["type"] == "Privé"].drop_duplicates(subset=["domaine"]).head(max_schools)
    print(f"Scraping {len(df)} ecoles privees...\n")

    all_contacts = []
    total = len(df)
    stats = {"found": 0, "no_access": 0, "empty": 0}

    for i, (_, row) in enumerate(df.iterrows()):
        domaine = row.get("domaine", "")
        if not domaine:
            continue
        base_url = f"https://{domaine}"

        info = _scrape_school(domaine, base_url, session, HEADERS, TIMEOUT)

        if not info["names"] and not info["linkedins"] and not info["emails"]:
            stats["empty"] += 1
            if (i + 1) % 25 == 0:
                print(f"  [{i + 1}/{total}] {domaine:40s} -> 0")
            continue

        # Enregistrer les contacts
        if info["names"]:
            for name, role in info["names"].items():
                all_contacts.append(
                    {
                        "domaine": domaine,
                        "prospect_nom": row.get("nom", ""),
                        "pays": row.get("pays", ""),
                        "contact_nom": name,
                        "contact_titre": role,
                        "linkedin_url": " | ".join(info["linkedins"])
                        if info["linkedins"]
                        else "",
                        "email": " | ".join(info["emails"]) if info["emails"] else "",
                        "source": "web_scrape",
                    }
                )
            stats["found"] += 1
            print(f"  [{i + 1}/{total}] {domaine:40s} -> {len(info['names'])} contacts")
        else:
            all_contacts.append(
                {
                    "domaine": domaine,
                    "prospect_nom": row.get("nom", ""),
                    "pays": row.get("pays", ""),
                    "contact_nom": "",
                    "contact_titre": "",
                    "linkedin_url": " | ".join(info["linkedins"])
                    if info["linkedins"]
                    else "",
                    "email": " | ".join(info["emails"]) if info["emails"] else "",
                    "source": "web_scrape",
                }
            )
            if info["linkedins"]:
                print(f"  [{i + 1}/{total}] {domaine:40s} -> LinkedIn trouve")
                stats["found"] += 1
            else:
                print(f"  [{i + 1}/{total}] {domaine:40s} -> email trouve")

    out_path = Path(__file__).parent.parent / output_csv
    if all_contacts:
        out_df = pd.DataFrame(all_contacts)
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\nScraping termine: {len(all_contacts)} contacts -> {out_path}")
        print(f"  Ecoles avec contacts: {out_df['domaine'].nunique()}")
        print(f"  Contacts avec role: {(out_df['contact_titre'] != '').sum()}")
        print(f"  Emails trouves: {(out_df['email'] != '').sum()}")
    else:
        print("\nAucun contact trouve.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "import":
        import_contacts_from_n8n()
    elif len(sys.argv) > 1 and sys.argv[1] == "scrape":
        run_direct_scrape()
    else:
        export_chauds_for_n8n()
