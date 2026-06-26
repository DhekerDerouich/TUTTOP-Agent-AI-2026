# TUT'TOP — Agent IA unifié

## Architecture

```
app.py                          # Point d'entrée Streamlit (navigation 4 pages)
dashboard/
├── app.py                      # (same as root app.py)
├── utils/
│   ├── data_loader.py          # Chargement prospects (120k/19k/run) + contacts + veille + subventions
│   └── runner.py               # Lancement pipeline en subprocess (encoding utf-8)
├── pages/
│   ├── 1_Prospection.py        # Lancer pipeline + filtrer + visualiser + fiche détaillée + exporter
│   ├── 2_Veille.py             # Lancer veille + checkpoint + visualiser
│   ├── 3_Subventions.py        # Lancer + filtrer (région, statut, priorité, type aide)
│   └── 4_Tableau_de_bord.py    # Stats globales
run.py                          # Pipeline unifié prospection/veille/subventions
agent/
├── subventions_models.py       # Modèle Subvention enrichi (20+ champs)
├── subventions_nodes.py        # Nœuds subventions avec prompt amélioré (format YYYY-MM-DD)
tools/
├── contact_collector.py        # Scraping contacts + export n8n + Hunter.io
├── apollo_collector.py         # Apollo.io API contacts
└── scraper_emails_massif.py    # Scraping massif emails (3 phases)
data/
├── all_data_enriched.csv       # 120 528 prospects bruts (tous pays, toutes sources)
├── prospect_chauds.xlsx        # 19 533 prospects qualifiés (18 pays, Chaud/Tiède)
├── contacts.csv                # 21 contacts scrapés (16 domaines)
├── cache_emails.json           # 11 578 domaines scrapés (homepage + deep)
├── veille.xlsx                 # 63 hackathons + 20 événements
├── veille_unified.xlsx         # 9 entrées
├── subventions_all.xlsx        # 19 subventions (20 colonnes)
└── state_veille.json           # Checkpoint veille (reprise)
```

## Pipelines

| Pipeline | Source | Volume | Statut |
|----------|--------|--------|--------|
| Prospection | API + web scraping + LLM | 120k bruts → 19k qualifiés | ✅ |
| Veille événementielle | Google + web | 83 événements | ✅ |
| Subventions | Web + LLM extraction | 19 subventions (20 colonnes) | ✅ |

## Dashboard Streamlit

- **Prospection**: Lancement pipeline, filtres (pays, type, score, recherche), tableau, fiche détaillée avec contacts, export CSV/XLSX
- **Veille**: Lancement avec itérations, score min, checkpoint (reprise), visualisation
- **Subventions**: Lancement, filtres (région, statut, priorité, type aide)
- **Tableau de bord**: Stats globales

## Fiche prospect visuelle (5.4)

- Recherche par nom dans les résultats filtrés
- Carte HTML avec badges (score coloré, type, pays)
- Infos: site web (lien), email, téléphone, localisation
- Contacts associés (nom, titre, email, LinkedIn)
- Données contacts issues du scraping web + Apollo.io

## Fonctionnement

- **LLM**: Groq (llama-3.1-8b-instant) via LangChain
- **LangSmith**: Réactivé (projet `TUTTOP-agent-unified`)
- **Mode rapide**: Skip API/Web pour la prospection
- **Checkpoint veille**: Reprise interrompue en AJOUTANT aux résultats existants
- **Priorité fichiers**: veille.xlsx (83 entrées) > veille_unified.xlsx (9 entrées)
- **Encoding**: UTF-8 forcé dans runner.py (évite erreurs cp1252)

## Perspectives

- **5.3 Recherche contacts**: Outils existants (Apollo, scraping, Hunter) non intégrés au pipeline unifié
- **Export PDF** de la fiche prospect
- **Ciblage campagne email** depuis les contacts trouvés
