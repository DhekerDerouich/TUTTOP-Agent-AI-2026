# Projet TUT'TOP — Agent IA de prospection EdTech

## Objectif
Agent IA autonome qui collecte, classe, nettoie et qualifie des prospects (établissements scolaires) dans toute l'Europe + Tunisie pour de la prospection EdTech.

---

## Architecture

```
agent_identification/
├── main.py                       ← Entry point (CLI argparse)
├── models.py                     ← Modèles Pydantic (Prospect, SchoolType)
├── exploration.ipynb             ← Notebook d'analyse
├── generate_final_datasets.py    ← Export CSV par pays
│
├── agent/
│   ├── classifier.py             ← Classification Privé/Public (keywords + LLM)
│   ├── cleaner.py                ← Nettoyage (sites, téléphone, dédup)
│   ├── qualifier.py              ← Scoring 0-100 (Chaud/Tiède/Froid)
│   ├── llm.py                    ← Interface LLM (Ollama/Groq/Gemini/OpenAI)
│   ├── graph.py                  ← Graphe LangGraph (orchestration)
│   ├── nodes.py                  ← Nœuds du pipeline
│   └── orchestrator.py          ← Décide la prochaine action via LLM
│
├── config/
│   └── sources.json              ← 13 sources de données
│
├── core/
│   ├── deduplicator.py           ← Déduplication
│   └── extractor.py              ← Normalisation des données brutes
│
├── tools/
│   ├── api_collector.py          ← APIs (Wikidata, OSM, OData, CKAN...)
│   ├── web_collector.py          ← Scraping (Google, Bing, pages jaunes)
│   └── prospect_search.py        ← Recherche dans CSV locaux
│
└── data/
    ├── all_data.csv              ← Master brut (121 011 prospects)
    ├── all_data_enriched.csv     ← Après pipeline (120 523)
    ├── france_final.csv
    ├── belgique_final.csv
    ├── suisse_final.csv
    └── tunisie_final.csv
```

---

## Pipeline de traitement

```
CSV brut → Classify (keywords + LLM) → Clean (dédup, normalisation) → Qualify (scoring) → Export
```

### 1. Classification (`classifier.py`)
- **Keywords multilingues** : 30 patterns Privé, 170+ patterns Public en 20+ langues
- **LLM** : `qwen2.5:1.5b` (local, GTX 1650) pour les noms ambigus, par lots de 200

### 2. Nettoyage (`cleaner.py`)
- Uniformisation sites web, téléphones, localisations
- Déduplication par site_web ou nom+pays

### 3. Scoring (`qualifier.py`)
| Critère | Points |
|---------|--------|
| Type = Privé | +30 |
| Type = Public | +15 |
| A un site web | +20 |
| A un email | +15 |
| A un téléphone | +10 |
| Pays prioritaire | +15 |

Seuils : **Chaud ≥ 50**, **Tiède ≥ 20**, **Froid < 20**

---

## Résultats

| Métrique | Valeur |
|----------|--------|
| **Total prospects** | 121 011 (bruts) → 120 523 (nettoyés) |
| **Pays couverts** | 23 européens + Tunisie |
| **Classés Public** | 99 596 |
| **Classés Privé** | 13 429 |
| **Inconnus** | 7 498 (dont 4 990 Q-IDs Wikidata) |
| **Taux de classification** | 93.8 % |
| **Chaud** | 52 615 |
| **Tiède** | 48 515 |
| **Froid** | 19 393 |

### Efficacité classification

| Méthode | Classés | Temps |
|---------|---------|-------|
| Keywords originaux | 53 992 | instantané |
| Nouveaux keywords (vagues 1-3) | +7 074 | 5 sec |
| Ollama qwen2.5:1.5b (run 1) | +4 944 | ~1h45 |
| Ollama qwen2.5:1.5b (run 2) | +1 213 | ~28 min |

---

## Matériel & Outils

- **PC** : Dell G15 5510 (16 Go RAM, NVIDIA GTX 1650 4 Go)
- **OS** : Windows
- **Python 3.14**
- **Ollama** + `qwen2.5:1.5b` (986 Mo, GPU)
- **LangGraph** pour l'orchestration
- **APIs** : Groq ✅, OpenAI ❌ (quota épuisé), Google ❓

---

## Prochaines étapes

1. **Réduire les 7 498 Inconnus** — analyser les 3 721 vrais noms restants (Suède, Italie, UK), ajouter des keywords, tester `llama3.2:3b` ou Groq
2. **Améliorer le scoring** — nouveaux critères (réseaux sociaux, taille, notes)
3. **Nouvelle collecte** — autres pays et sources
4. **Dashboard / export CRM**
5. **Tests et robustesse**
