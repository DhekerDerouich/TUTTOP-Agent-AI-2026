import json
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from agent.subventions_models import Subvention
from agent.llm import get_llm


class SubventionsState(TypedDict):
    messages: Annotated[Sequence[dict], add_messages]
    subventions: list[Subvention]
    queries_executees: list[str]
    iteration: int
    max_iterations: int
    store: dict


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        description="5 requetes de recherche pour trouver des aides, subventions et appels a projets EdTech en France et Europe"
    )


SYSTEM_PROMPT_QUERIES = """Tu es un assistant specialise dans la veille de subventions publiques, appels a projets et programmes de financement pour l'education et l'innovation en France et en Europe.

Tu dois generer des requetes de recherche web pour trouver :
1. Des subventions publiques pour l'education et le numerique scolaire
2. Des appels a projets pour l'innovation dans l'education
3. Des programmes europeens de financement (Erasmus+, Horizon Europe…)
4. Des aides a la digitalisation des etablissements scolaires
5. Des programmes regionaux et nationaux (France 2030, Bpifrance, ANR…)

IMPORTANT : Les aides recherchees concernent TOUTE la France et l'Union Europeenne.
Ne te limite pas a une region specifique.

Annee courante : 2026

Genere 5 requetes courtes et precises en francais."""


def _get_llm():
    return get_llm(provider="groq", temperature=0.1)


def _chunk_data(data: list, size: int):
    return [data[i : i + size] for i in range(0, len(data), size)]


def _parse_json_from_llm(text: str) -> dict:
    import re

    text = text.strip()
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*\]", "]", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise


def generate_queries_subventions(state: SubventionsState) -> dict:
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    subventions = state.get("subventions", [])
    queries_done = state.get("queries_executees", [])

    print(f"\n{'=' * 60}")
    print(f"  [SUBVENTIONS] Iteration {iteration + 1}/{max_iter}")
    print(f"  Deja trouve: {len(subventions)} subventions")
    print(f"  Requetes deja executees: {len(queries_done)}")
    print(f"{'=' * 60}")

    context = f"Requetes deja utilisees: {', '.join(queries_done[-6:]) if queries_done else 'aucune'}"
    context += f"\nSubventions deja trouvees: {len(subventions)}"

    if not queries_done:
        queries = [
            "subvention education numerique France 2026",
            "appel a projets EdTech IA 2026",
            "financement digitalisation etablissements scolaires 2026",
            "programme Erasmus+ education formation 2026",
            "aide innovation pedagogique region 2026",
        ]
        return {
            "queries_executees": queries_done + queries,
            "iteration": iteration + 1,
            "store": state.get("store", {}),
        }

    llm = _get_llm()
    llm_structured = llm.with_structured_output(SearchQueries)

    result = llm_structured.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT_QUERIES},
            {
                "role": "user",
                "content": f"Contexte:\n{context}\n\nGenere 5 nouvelles requetes de recherche pour trouver des aides, subventions et appels a projets EdTech en France et en Europe en 2026.",
            },
        ]
    )

    new_queries = result.queries[:5] if hasattr(result, "queries") else []

    if not new_queries:
        new_queries = [
            "France 2030 appel a projets education 2026",
            "Bpifrance financement innovation educative 2026",
            "ANR programme prioritaire recherche education 2026",
            "Horizon Europe cluster education numerique 2026",
            "aides regionale digitalisation lycees college 2026",
        ]

    queries_all = queries_done + new_queries
    return {
        "queries_executees": queries_all,
        "iteration": iteration + 1,
        "store": state.get("store", {}),
    }


def search_tavily_subventions(state: SubventionsState) -> dict:
    import os
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

    queries = state.get("queries_executees", [])
    n_queries = min(5, len(queries))
    last_queries = queries[-n_queries:] if n_queries > 0 else queries

    print(f"\n  [TAVILY] Recherche subventions pour {len(last_queries)} requetes...")

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("    Pas de cle Tavily, skip")
        return {"store": state.get("store", {})}

    all_results = []

    for q in last_queries:
        print(f"    Requete: {q}")

        def _search(q):
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            return client.search(
                query=q,
                search_depth="advanced",
                max_results=5,
                time_range="year",
                include_answer=False,
            )

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_search, q)
                response = fut.result(timeout=20)
            for res in response.get("results", []):
                all_results.append(
                    {
                        "title": res.get("title", ""),
                        "url": res.get("url", ""),
                        "snippet": res.get("content", "")[:500],
                        "page_content": res.get("content", ""),
                        "query": q,
                        "source_engine": "tavily",
                    }
                )
            print(f"      -> {len(response.get('results', []))} resultats")
        except FutureTimeout:
            print(f"      -> Timeout (20s depasse)")
        except Exception as ex:
            print(f"      -> Erreur: {ex}")

    store = dict(state.get("store", {}))
    existing = store.get("tavily_data", [])
    store["tavily_data"] = existing + all_results
    print(f"    Total tavily_data: {len(store['tavily_data'])} entrees")
    return {"store": store}


def search_duckduckgo_subventions(state: SubventionsState) -> dict:
    queries = state.get("queries_executees", [])
    n_queries = min(5, len(queries))
    last_queries = queries[-n_queries:] if n_queries > 0 else queries

    print(
        f"\n  [DUCKDUCKGO] Recherche subventions pour {len(last_queries)} requetes..."
    )

    all_results = []

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    import time as _time

    for q in last_queries:
        print(f"    Requete: {q}")
        try:
            from ddgs import DDGS

            def _search(q):
                results = []
                with DDGS() as ddgs:
                    results = list(ddgs.text(q, max_results=3))
                return results

            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_search, q)
                results = fut.result(timeout=10)
            for res in results:
                all_results.append(
                    {
                        "title": res.get("title", ""),
                        "url": res.get("href", ""),
                        "snippet": res.get("body", "")[:500],
                        "page_content": res.get("body", ""),
                        "query": q,
                        "source_engine": "duckduckgo",
                    }
                )
            print(f"      -> {len(results)} resultats")
            _time.sleep(0.5)
        except FutureTimeout:
            print(f"      -> Timeout (10s depasse)")
        except Exception as ex:
            print(f"      -> Erreur: {ex}")

    store = dict(state.get("store", {}))
    existing = store.get("duckduckgo_data", [])
    store["duckduckgo_data"] = existing + all_results
    print(f"    Total duckduckgo_data: {len(store['duckduckgo_data'])} entrees")
    return {"store": store}


TUTTOP_DESC_SUB = """
TUT'TOP est une plateforme d'infrastructure de tutorat propulsee par l'IA.
Fonctionnalites cles :
- Chatbot repondant aux questions sur les cours (depuis PDF, documents, chapitres)
- Generation automatique de quiz, cartes mentales et flashcards
- Correction intelligente avec analyse des erreurs
- Systeme anti-triche par detection IA
- CRM scolaire avec suivi des candidatures et pipeline d'admissions
- Automatisation des documents (contrats, bulletins, conventions)
- Concu pour les etudiants, les enseignants et les etablissements
"""

SCORING_CRITERIA_SUB = """
Critères de score strategique (0-10) :

1. Alignement TUT'TOP (poids fort) :
   - Finance directement l'achat d'une solution EdTech/logiciel pedagogique = 10
   - Finance la digitalisation/l'innovation des etablissements = 7
   - Finance la formation ou la recherche en education = 5
   - Non lie a l'education ou au numerique = 1

2. Deadline (poids moyen) :
   - Dans les 3 mois = 10
   - Dans les 6 mois = 7
   - Dans l'annee = 4
   - Pas de deadline ou permanente = 2

3. Montant (poids moyen) :
   - > 500 000€ = 10
   - 100 000€ a 500 000€ = 7
   - < 100 000€ = 4
   - Non specifie = 2

4. Eligibilite (poids fort) :
   - Ecoles/etablissements directement eligibles = 10
   - Entreprises/labos/associations = 7
   - Familles/individus uniquement = 3
"""


def extract_subventions(state: SubventionsState) -> dict:
    store = dict(state.get("store", {}))
    tavily_data = store.get("tavily_data", [])
    duckduckgo_data = store.get("duckduckgo_data", [])
    raw_data = tavily_data + duckduckgo_data
    subventions = list(state.get("subventions", []))

    print(
        f"\n  [EXTRACTION] Analyse de {len(raw_data)} entrees (tavily={len(tavily_data)}, duckduckgo={len(duckduckgo_data)})"
    )

    if not raw_data:
        print("    Aucune donnee a analyser")
        return {"subventions": subventions}

    chunks = _chunk_data(raw_data, 4)

    for chunk in chunks:
        textes = []
        for item in chunk:
            q = item.get("query", "")
            textes.append(
                f"- {item.get('title', '')} | {item.get('url', '')} | Query: {q}"
            )

        content = "\n\n---\n\n".join(textes)

        from datetime import date as _today_date

        _today = _today_date.today().strftime("%Y-%m-%d")

        PROMPT = (
            """Tu es un assistant qui extrait des aides, subventions et appels a projets depuis des pages web.

REGLE IMPORTANTE : Ne retourne que des programmes applicables en France ou dans l'Union Europeenne.
IGNORE les programmes destines a d'autres pays (Maroc, Afrique, Cameroun, etc.).

REGLE FORMAT DATE : TOUTES les dates doivent etre au format YYYY-MM-DD (ex: 2026-09-15).
Exemple : "15 septembre 2026" -> "2026-09-15". "cloture le 30/04/2026" -> "2026-04-30".

REGLE DEADLINE : Tu DOIS trouver la deadline exacte (YYYY-MM-DD) si elle est mentionnee.
Ne mets PAS "Variable" si une date, meme partielle, est donnee. Cherche dans le titre, le snippet et l'URL.
Mets "Variable" UNIQUEMENT si absolument aucune information de date n'est disponible.

REGLE DATE PUBLICATION : Extrais la date de publication si mentionnee. Sinon, deduis-la depuis l'annee.

REGLE LIEN OFFICIEL : Si le texte officiel (arrete, decret, page gouvernementale) a une URL differente de la page web source, mets-la dans "lien_officiel". Sinon, mets la meme URL que "url".

REGLE PUBLIC CIBLE : Utilise TOUJOURS le singulier et le point-virgule comme separateur.
Exemples: "ecole", "universite", "startup", "ecole;universite", "entreprise;association", "collectivite".
Ne mets PAS de pluriel, PAS de pipe (|), PAS de virgule.

REGLE REGION : Determine la region geographique. Valeurs possibles :
- "National" si toute la France
- "Europe" si UE
- "PACA", "Ile-de-France", "Occitanie", etc. si region specifique
- "Alpes-Maritimes", "Paris", etc. si departement/ville
- Sinon laisse vide

REGLE MOTS_CLES : Genere 3-5 mots-cles separes par point-virgule en rapport avec l'aide.
Exemple : "digitalisation;education;numerique;subvention;IA"

REGLE TYPE_AIDE : Classe l'aide selon son utilisation pour TUT'TOP :
- "vente" si l'aide permet a des etablissements d'acheter des solutions (TUT'TOP peut vendre)
- "rd" si l'aide finance de la R&D, innovation, developpement (TUT'TOP peut candidater)
- "veille" si c'est une information generale sans opportunite directe

REGLE STATUT : Determine si l'appel est encore ouvert :
- "ouvert" si la deadline est future ou pas encore passee
- "ferme" si la deadline est passee
- "a_venir" si l'appel n'a pas encore ouvert (date publication future ou non precisée)

REGLE PRIORITE : Deduis-la du score strategique :
- score 8-10 -> "Elevee"
- score 4-7 -> "Moyenne"
- score 0-3 -> "Faible"

Contexte TUT'TOP :
"""
            + TUTTOP_DESC_SUB
            + """
Quand tu rediges la description et la raison, explique comment cette aide peut beneficier a TUT'TOP ou a ses prospects.
Exemple raison : "Les lycees peuvent utiliser ce fonds pour financer l'achat de solutions EdTech comme TUT'TOP"
Exemple pertinence : "Elevée - finance directement la digitalisation des etablissements"

Types possibles :
- "subvention_publique" : aide directe (ARS, bourses, fonds sociaux…)
- "appel_projets" : appel a projets (PPR, France 2030, i-Demo…)
- "programme_financement" : programme cadre (Erasmus+, Horizon Europe, Bpifrance…)

Retourne UNIQUEMENT un JSON valide (sans markdown, sans backticks) avec cette structure exacte:
{
  "subventions": [
    {
      "nom": "string",
      "type": "subvention_publique|appel_projets|programme_financement",
      "sous_type": "string (ex: ARS, fonds_social, bourse, PPR, i-Demo, Erasmus+...)",
      "organisme": "string (ANR, Bpifrance, Commission Europeenne, Region, Education Nationale...)",
      "region": "National|Europe|PACA|Ile-de-France|Occitanie|... OBLIGATOIRE",
      "public_cible": "ecole|universite|startup|ecole;universite|... OBLIGATOIRE — singulier, point-virgule",
      "deadline": "YYYY-MM-DD — OBLIGATOIRE : trouve la date exacte, pas Variable par defaut",
      "date_publication": "YYYY-MM-DD — OBLIGATOIRE : extrais la date de publication",
      "montant": "string (ex: 466€/enfant, 350K-1.5M€, Variable...)",
      "eligibilite": "string (qui peut postuler: ecoles, entreprises, laboratoires, familles...)",
      "mots_cles": "digitalisation;education;numerique;IA;subvention — OBLIGATOIRE",
      "type_aide": "vente|rd|veille — OBLIGATOIRE",
      "statut": "ouvert|ferme|a_venir — OBLIGATOIRE",
      "priorite": "Elevee|Moyenne|Faible — OBLIGATOIRE (score 8-10=Elevee, 4-7=Moyenne, 0-3=Faible)",
      "score_strategique": 0,
      "pertinence": "Elevee|Moyenne|Faible",
      "raison": "courte explication montrant pourquoi cette aide est utile pour TUT'TOP ou ses prospects",
      "url": "string",
      "lien_officiel": "URL du texte officiel si disponible, sinon meme URL",
      "date_derniere_verification": \""""
            + _today
            + """\",
      "description": "string",
      "thematiques": ["IA", "education", "numerique", "innovation", ...]
    }
  ]
}
"""
            + SCORING_CRITERIA_SUB
            + "\n\nPages web a analyser:\n"
            + content
        )

        llm = _get_llm()

        try:
            response = llm.invoke(
                [
                    {
                        "role": "system",
                        "content": "Tu es un assistant specialise dans l'extraction de donnees depuis des pages web. Tu ne reponds qu'en JSON valide.",
                    },
                    {"role": "user", "content": PROMPT},
                ]
            )

            data = _parse_json_from_llm(response.content)

            for s_data in data.get("subventions", []):
                s = Subvention(
                    **{k: v for k, v in s_data.items() if k in Subvention.model_fields}
                )
                if s.nom and not any(
                    ex.nom.lower() == s.nom.lower() for ex in subventions
                ):
                    subventions.append(s)

            print(f"    Extrait: {len(data.get('subventions', []))} subventions")

        except Exception as ex:
            print(f"    Erreur extraction: {ex}")
            continue

    subventions = [
        s for s in subventions if s.nom and s.nom.lower() not in ("string", "")
    ]

    subventions = _filter_france(subventions)

    print(f"  Total: {len(subventions)} subventions trouvees (France/UE)")

    return {"subventions": subventions}


_FRANCE_KEYWORDS = [
    "france",
    "français",
    "francaise",
    "française",
    "region",
    "departement",
    "commune",
    "education nationale",
    "ministere",
    "anr",
    "bpifrance",
    "france 2030",
    "france2030",
    "caisse des depots",
    "banque des territoires",
    "commission europeenne",
    "union europeenne",
    "europeenne",
    "europeen",
    "erasmus",
    "horizon europe",
    "europe",
    "region sud",
    "provence",
    "paca",
    "côte d'azur",
    "cote d'azur",
    "iledefrance",
    "île-de-france",
    "auvergne",
    "rhone",
    "bretagne",
    "nouvelle-aquitaine",
    "occitanie",
    "hauts-de-france",
    "grand est",
    "normandie",
    "bourgogne",
    "centre-val de loire",
    "pays de la loire",
    "corse",
    "gouvernement francais",
    "gouvernement français",
    "education",
    "enseignement",
    "scolaire",
    "lycee",
    "college",
    "ecole",
]


def _filter_france(subventions: list) -> list:
    kept = []
    removed = 0
    for s in subventions:
        nom = (s.nom or "").lower()
        org = (s.organisme or "").lower()
        desc = (s.description or "").lower()
        text = f"{nom} {org} {desc}"
        has_france = any(kw in text for kw in _FRANCE_KEYWORDS)
        if has_france:
            kept.append(s)
        else:
            removed += 1
    if removed:
        print(
            f"      Filtre France: {removed} subvention(s) retiree(s) (hors France/UE)"
        )
    return kept


def decide_next_subventions(state: SubventionsState) -> str:
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    subventions = state.get("subventions", [])
    total = len(subventions)

    print(
        f"\n  [DECISION] Iteration {iteration + 1}/{max_iter}, total: {total} subventions"
    )

    if iteration + 1 >= max_iter:
        print("    -> FIN: iteration max atteinte")
        return "end"

    print("    -> CONTINUER: nouvelle iteration")
    return "continue"
