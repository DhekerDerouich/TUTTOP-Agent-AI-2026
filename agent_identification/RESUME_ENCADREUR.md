# TUT'TOP — Agent IA unifié de prospection EdTech

## Rapport technique — Juin 2026

---

## 1. L'agent conversationnel : cœur du projet

Un **graphe d'état unifié (LangGraph)** orchestre l'ensemble des tâches. Chaque nœud est une fonction Python qui reçoit et modifie un état global (`UnifiedState`).

### Architecture du graphe

```
                    ┌─────────────────────────────────────┐
                    │          UnifiedState                │
                    │  prospects: [], hackathons: [],      │
                    │  subventions: [], queries: [], ...   │
                    └─────────────────────────────────────┘
                                      │
                    ┌─────────────────┴──────────────────┐
                    │         router_principal            │
                    │  (prospection / veille / subventions)│
                    └─────────────────┬──────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   ┌───────────┐              ┌──────────────┐            ┌──────────────┐
   │PROSPECTION│              │   VEILLE     │            │ SUBVENTIONS  │
   └─────┬─────┘              └──────┬───────┘            └──────┬───────┘
         │                           │                           │
   ┌─────┴──────┐              ┌─────┴──────┐              ┌─────┴──────┐
   │CSV → API   │              │Tavily search│             │Tavily search│
   │→ Web → LLM │              │DDG search   │             │DDG search   │
   │classify→   │              │→ extract    │             │→ extract    │
   │clean→ qualify│            │→ dedup      │             │→ dedup      │
   └───────────┘              └────────────┘              └────────────┘
```

### Nœuds du graphe (fichier `agent/unified_graph.py`)

| Nœud | Rôle | Source de données |
|------|------|------------------|
| `find_prospects_csv` | Lecture fichiers CSV | Fichiers OpenData (annuaires établissements) |
| `find_prospects_api` | Requêtes API | Google Maps API |
| `find_prospects_web` | Recherche web | Tavily Search (web crawling) |
| `classify_types` | Classification LLM | Groq (llama-3.1-8b-instant) |
| `clean_prospects` | Nettoyage | Regex + règles métier |
| `qualify_prospects` | Scoring Chaud/Tiède/Froid | LLM + règles (site web valide, email présent, etc.) |
| `search_tavily_veille` | Recherche événements EdTech | Tavily API |
| `search_duckduckgo_veille` | Recherche événements EdTech | DuckDuckGo API |
| `extract_veille` | Extraction LLM → modèles Hackathon/Evenement | Groq |
| `search_tavily_subventions` | Recherche aides | Tavily API |
| `search_duckduckgo_subventions` | Recherche aides | DuckDuckGo API |
| `extract_subventions` | Extraction LLM → modèle Subvention (20 champs) | Groq |

### Exemple de flux : mode prospection

```
1. find_prospects_csv  → charge 120k lignes depuis les fichiers OpenData
2. find_prospects_api  → enrichit avec Google Maps (coordonnées, site web)
3. find_prospects_web  → enrichit avec Tavily (emails, téléphones)
4. classify_types      → LLM détermine Privé/Public/Inconnu
5. clean_prospects     → normalise, déduplique, valide les URLs
6. qualify_prospects   → LLM attribue un score (0-100) + qualification
```

### Exemple de flux : mode veille

```
1. search_tavily_veille    → requêtes web EdTech
2. search_duckduckgo_veille → requêtes web EdTech
3. extract_veille          → LLM extrait nom, date, lieu, score (0-10)
4. déduplication           → par nom (garder le meilleur score)
```

## 2. Modèles de données (Pydantic)

### UnifiedState (état global)

```python
class UnifiedState(TypedDict):
    task: str                          # prospection | veille | subventions
    prospects: list[Prospect]          # résultats prospection
    hackathons: list[Hackathon]        # résultats veille
    evenements: list[Evenement]        # résultats veille
    subventions: list[Subvention]      # résultats subventions
    queries_executees: list[str]       # historique requêtes
    pays: str, statut: str, limit: int # paramètres prospection
    iteration: int, max_iterations: int
    store: dict                        # données intermédiaires
```

### Prospect (10 champs)
`nom`, `type` (Privé/Public/Inconnu), `localisation`, `site_web`, `email`, `telephone`, `source` (csv/api/web), `pays`, `score` (0-100), `qualification` (Chaud/Tiède/Froid)

### Hackathon / Evenement (9 champs)
`nom`, `type`, `date`, `lieu`, `description`, `url`, `score_strategique` (0-10), `raison`, `source_engine` (tavily/duckduckgo)

### Subvention (20 champs)
`nom`, `type`, `sous_type`, `organisme`, `region`, `public_cible`, `deadline`, `date_publication`, `montant`, `eligibilite`, `mots_cles`, `type_aide`, `statut`, `priorite`, `score_strategique` (0-10), `pertinence`, `raison`, `url`, `lien_officiel`, `date_derniere_verification`

## 3. Dashboard Streamlit (interface utilisateur)

### Pages

| Page | Fonctionnalités |
|------|----------------|
| **Prospection** | Lancer pipeline, filtrer (pays, type, score, recherche), tableau, fiche détaillée avec contacts, export CSV/XLSX |
| **Veille** | Lancer pipeline (itérations, score min, checkpoint visualiser |
| **Subventions** | Lancer pipeline, filtrer (région, statut, priorité, type aide) |
| **Tableau de bord** | Statistiques globales (120k prospects, 83 événements, 19 subventions) |

### Lancement des pipelines depuis le dashboard

Chaque page de lancement appelle le même code que la CLI via subprocess :
```
dashboard/utils/runner.py → run.py --mode [prospection|veille|subventions]
```

## 4. Gestion des données : merge au lieu d'overwrite

**Problème :** les pipelines écrasaient les résultats précédents.

**Solution :** chaque export fusionne avec l'existant + déduplication :

| Pipeline | Fichier exporté | Clé de déduplication | Checkpoint (JSON) |
|----------|----------------|----------------------|-------------------|
| Prospection | `prospects_all_{pays}.csv` | `nom` + `site_web` | ❌ |
| Veille | `veille.xlsx` (2 sheets) | `nom` | ✅ `state_veille.json` |
| Subventions | `subventions_all.xlsx` | `Nom` | ✅ `state_subventions.json` |

### Checkpoints (reprise après interruption)

```python
# Exemple : sauvegarde incrémentielle de l'état
save_checkpoint(values)       # → data/state_veille.json
save_checkpoint_subventions(values)  # → data/state_subventions.json

# Reprise
python run.py --mode veille --load-checkpoint
```

## 5. Stack technique

| Couche | Technologie | Rôle |
|--------|-------------|------|
| Interface utilisateur | **Streamlit 1.58.0** | Dashboard multi-pages |
| LLM | **Groq API** | Classification, extraction, scoring |
| Framework LLM | **LangChain** | Orchestration des appels LLM |
| Graphe d'état | **LangGraph** | Orchestration des nœuds |
| Traçage | **LangSmith** | Débogage et monitoring |
| Modèles | **Pydantic v2** | Validation des données |
| Stockage | **Pandas + openpyxl** | CSV et Excel |
| Environnement | **Python 3.14** | Windows |

## 6. Volumes de données

| Données | Volume | Source |
|---------|--------|--------|
| Prospects bruts | **120 528** | Fichiers OpenData (RNE, ONISEP, etc.) |
| Prospects qualifiés Chaud/Tiède | **19 533** | Après classification + scoring LLM |
| Contacts scrapés | **21** (16 domaines) | Scraping pages équipe |
| Cache emails | **11 578** domaines | Scraping massif 3 phases |
| Événements EdTech | **83** | Tavily + DuckDuckGo + extraction LLM |
| Subventions | **19** | Tavily + DuckDuckGo + extraction LLM |

## 7. Outils périphériques (non intégrés au graphe)

| Outil | Usage | Statut |
|-------|-------|--------|
| `tools/apollo_collector.py` | Recherche contacts via API Apollo.io | Utilisable en CLI |
| `tools/scraper_emails_massif.py` | Scraping emails en 3 phases | Utilisable en CLI |
| `tools/contact_collector.py` | Scraping pages équipe + Hunter.io | Utilisable en CLI |

## 8. Commandes d'exécution

```bash
# Dashboard
streamlit run app.py

# Prospection France (mode rapide, skip API/Web)
python run.py --mode prospection --pays france --quick

# Prospection complète
python run.py --mode prospection --pays france --limit 5000

# Veille avec reprise
python run.py --mode veille --load-checkpoint --max-iterations 5

# Subventions avec reprise
python run.py --mode subventions --load-checkpoint --subventions-max-iterations 3

# Pipeline complet
python run.py --mode all --quick --load-checkpoint

# Dry run (visualiser le graphe)
python run.py --dry-run
```
