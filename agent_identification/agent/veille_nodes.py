import json
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from agent.veille_models import Hackathon, Evenement
from agent.llm import get_llm


class VeilleState(TypedDict):
    messages: Annotated[Sequence[dict], add_messages]
    hackathons: list[Hackathon]
    evenements: list[Evenement]
    queries_executees: list[str]
    iteration: int
    max_iterations: int
    store: dict


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        description="5 requetes de recherche pour trouver des hackathons et evenements EdTech dans la region Alpes-Maritimes et Monaco"
    )


SYSTEM_PROMPT_QUERIES = """Tu es un assistant specialise dans la veille de hackathons et evenements EdTech dans la region Alpes-Maritimes et Monaco.

Zone de recherche EXCLUSIVE : Alpes-Maritimes, Nice, Sophia Antipolis, Cannes, Antibes, Grasse, Menton, Monaco, Cote d'Azur, Paca.

Tu dois generer des requetes de recherche web pour trouver :
1. Des hackathons (IA, education, innovation pedagogique, numerique educatif)
2. Des conferences EdTech
3. Des salons educatifs et evenements d'innovation
4. Des competitions et challenges dans l'education

IMPORTANT : Limite-toi STRICTEMENT a la region Alpes-Maritimes / Cote d'Azur / Monaco / Paca.
Ne propose PAS de requetes pour Paris, Lyon, Bordeaux, ou d'autres regions.

Annee courante : 2026

Genere 5 requetes courtes et precises en francais."""


def _get_llm():
    return get_llm(provider="groq", temperature=0.1)


def generate_queries(state: VeilleState) -> dict:
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    hackathons = state.get("hackathons", [])
    evenements = state.get("evenements", [])
    queries_done = state.get("queries_executees", [])

    print(f"\n{'=' * 60}")
    print(f"  Iteration {iteration + 1}/{max_iter}")
    print(f"  Deja trouve: {len(hackathons)} hackathons, {len(evenements)} evenements")
    print(f"  Requetes deja executees: {len(queries_done)}")
    print(f"{'=' * 60}")

    context = f"Requetes deja utilisees: {', '.join(queries_done[-6:]) if queries_done else 'aucune'}"
    context += f"\nHackathons deja trouves: {len(hackathons)}"
    context += f"\nEvenements deja trouves: {len(evenements)}"

    llm = _get_llm()
    llm_structured = llm.with_structured_output(SearchQueries)

    if not queries_done:
        queries = [
            "hackathon IA education innovation Sophia Antipolis 2026",
            "concours IA data science Alpes-Maritimes 2026",
            "conference EdTech Monaco Cote d'Azur 2026",
            "salon education orientation innovation Nice Paca 2026",
            "competition startup etudiante Grasse Antibes 2026",
        ]
        return {
            "queries_executees": queries_done + queries,
            "iteration": iteration + 1,
            "store": state.get("store", {}),
        }

    result = llm_structured.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT_QUERIES},
            {
                "role": "user",
                "content": f"Contexte:\n{context}\n\nGenere 5 nouvelles requetes de recherche pour trouver des hackathons et evenements EdTech dans la region Alpes-Maritimes / Cote d'Azur / Monaco en 2026.",
            },
        ]
    )

    new_queries = result.queries[:5] if hasattr(result, "queries") else []

    if not new_queries:
        new_queries = [
            "hackathon IA apprentissage automatique Nice 2026",
            "salon EdTech innovation educative Sophia 2026",
            "concours startup IA Cote d'Azur 2026",
            "conference transformation digitale ecole Monaco 2026",
            "forum intelligence artificielle education Paca 2026",
        ]

    queries_all = queries_done + new_queries
    return {
        "queries_executees": queries_all,
        "iteration": iteration + 1,
        "store": state.get("store", {}),
    }


def search_tavily(state: VeilleState) -> dict:
    import os
    from tavily import TavilyClient

    queries = state.get("queries_executees", [])
    n_queries = min(5, len(queries))
    last_queries = queries[-n_queries:] if n_queries > 0 else queries

    print(f"\n  [TAVILY] Recherche web pour {len(last_queries)} requetes...")

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("    Pas de cle Tavily, skip")
        return {"store": state.get("store", {})}

    client = TavilyClient(api_key=api_key)
    all_results = []

    for q in last_queries:
        print(f"    Requete: {q}")
        try:
            response = client.search(
                query=q,
                search_depth="advanced",
                max_results=5,
                time_range="year",
                include_answer=False,
            )
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
        except Exception as ex:
            print(f"      -> Erreur: {ex}")

    store = dict(state.get("store", {}))
    existing = store.get("tavily_data", [])
    store["tavily_data"] = existing + all_results
    print(f"    Total tavily_data: {len(store['tavily_data'])} entrees")
    return {"store": store}


def search_duckduckgo(state: VeilleState) -> dict:
    queries = state.get("queries_executees", [])
    n_queries = min(5, len(queries))
    last_queries = queries[-n_queries:] if n_queries > 0 else queries

    print(f"\n  [DUCKDUCKGO] Recherche web pour {len(last_queries)} requetes...")

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
            print(f"      -> Timeout (15s depasse)")
        except Exception as ex:
            print(f"      -> Erreur: {ex}")

    store = dict(state.get("store", {}))
    existing = store.get("duckduckgo_data", [])
    store["duckduckgo_data"] = existing + all_results
    print(f"    Total duckduckgo_data: {len(store['duckduckgo_data'])} entrees")
    return {"store": store}


def llm_generate(state: VeilleState) -> dict:
    queries_done = state.get("queries_executees", [])
    n_queries = min(5, len(queries_done))
    last_queries = queries_done[-n_queries:] if n_queries > 0 else queries_done
    existing_h = state.get("hackathons", [])
    existing_e = state.get("evenements", [])

    print(f"\n  [LLM] Generation depuis les connaissances du modele...")
    print(f"    Themes: {last_queries}")

    TUTTOP_DESC = """TUT'TOP : plateforme IA de tutorat (chatbot cours, quiz, correction, anti-triche, CRM scolaire, automatisation documents)."""

    prompt = f"""Tu es un expert des evenements EdTech dans la region Alpes-Maritimes.

REGION : Nice, Sophia Antipolis, Cannes, Antibes, Grasse, Menton, Monaco.
DATES : Exclus tout evenement avant le 17 juin 2026. Annees 2026-2027.
Themes : {", ".join(last_queries)}

{TUTTOP_DESC}

Genere 5 hackathons ET 5 evenements (conferences/salons/competitions) realistes pour la region.

Retourne UNIQUEMENT ce JSON, sans texte avant/apres, sans backticks :
{{"hackathons":[{{"nom":"","date_debut":"JJ/MM/AAAA","date_fin":"JJ/MM/AAAA","lieu":"Ville","description":"","conditions":"equipe,niveau,prix","url":"","type":"Hackathon","thematiques":["IA"],"strategique":"Oui","score_strategique":8,"raison":"","pertinence_tuttop":"","source":"connaissance LLM"}}],"evenements":[{{"nom":"","type":"Conference","date":"JJ/MM/AAAA","lieu":"Ville","description":"","url":"","thematiques":["IA"],"strategique":"Oui","score_strategique":8,"raison":"","pertinence_tuttop":"","source":"connaissance LLM"}}]}}"""

    llm = _get_llm()
    response = llm.invoke(
        [
            {
                "role": "system",
                "content": "Tu es un assistant specialise dans les evenements EdTech de la region Paca. Ne reponds qu'en JSON valide, sans texte.",
            },
            {"role": "user", "content": prompt},
        ]
    )

    import re as _re2

    text = response.content.strip()
    text = _re2.sub(r"```(?:json)?\s*", "", text)

    if not text or text == "":
        print(f"    LLM a retourne une reponse vide")
        return {"hackathons": existing_h, "evenements": existing_e}

    result = {"hackathons": [], "evenements": []}
    found = False
    for m in _re2.finditer(r"\{.*\}", text, _re2.DOTALL):
        try:
            candidate = m.group()
            candidate = _re2.sub(r",\s*}", "}", candidate)
            candidate = _re2.sub(r",\s*\]", "]", candidate)
            parsed = json.loads(candidate)
            if "hackathons" in parsed or "evenements" in parsed:
                result = parsed
                found = True
                break
        except json.JSONDecodeError:
            continue

    if not found:
        print(f"    LLM: aucun JSON valide trouve dans la reponse ({len(text)} chars)")
        print(f"    Debut reponse: {text[:200]}")

    new_h, new_e = [], []
    for h_data in result.get("hackathons", []):
        h = Hackathon(
            **{k: v for k, v in h_data.items() if k in Hackathon.model_fields}
        )
        if h.nom and not any(ex.nom.lower() == h.nom.lower() for ex in existing_h):
            new_h.append(h)
    for e_data in result.get("evenements", []):
        e = Evenement(
            **{k: v for k, v in e_data.items() if k in Evenement.model_fields}
        )
        if e.nom and not any(ex.nom.lower() == e.nom.lower() for ex in existing_e):
            new_e.append(e)

    existing_h.extend(new_h)
    existing_e.extend(new_e)

    existing_h = _filter_relevant_topics(existing_h, "hackathon")
    existing_e = _filter_relevant_topics(existing_e, "evenement")
    existing_h = _fill_empty_scores(existing_h)
    existing_e = _fill_empty_scores(existing_e)
    existing_h, existing_e = _deduplicate_events(existing_h, existing_e)

    print(
        f"    Genere par le LLM: {len(new_h)} hackathons, {len(new_e)} evenements "
        f"(total {len(existing_h)} hackathons, {len(existing_e)} evenements)"
    )
    return {"hackathons": existing_h, "evenements": existing_e}


import re as _re
from datetime import datetime, date


TODAY = date(2026, 6, 16)


_MONTHS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_MONTHS_EN = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_ALL_MONTHS = {**_MONTHS_FR, **_MONTHS_EN}


def _parse_date_to_date(date_str) -> date | None:
    """Parse a date string.

    Returns:
        (year, month, day) tuple if full date, (year, month) tuple if month-only,
        year int if year-only, or None if unparseable.
    """
    if not isinstance(date_str, str):
        return None
    s = date_str.strip()
    if not s or s.lower() in ("tba", "non specifie", "à venir", "nan"):
        return None

    if "jj" in s.lower() or "mm" in s.lower() or "aaaa" in s.lower():
        return None

    m = _re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return ("full", date(y, mo, d))
        except ValueError:
            return None

    m = _re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return ("full", date(y, mo, d))
        except ValueError:
            return None

    m = _re.match(r"^(\d{1,2})/(\d{4})$", s)
    if m:
        return ("month", int(m.group(2)), int(m.group(1)))

    m = _re.match(r"^(\d{4})-(\d{1,2})$", s)
    if m:
        return ("month", int(m.group(1)), int(m.group(2)))

    m = _re.match(r"^(\d{4})$", s)
    if m:
        return ("year", int(m.group(1)))

    sl = s.lower()
    for month_name, month_num in _ALL_MONTHS.items():
        if month_name in sl:
            m_year = _re.search(r"\b(20\d{2})\b", s)
            m_day = _re.match(r"^(\d{1,2})\s", s)
            if m_year:
                y = int(m_year.group(1))
                if m_day:
                    try:
                        return ("full", date(y, month_num, int(m_day.group(1))))
                    except ValueError:
                        return None
                return ("month", y, month_num)

    return None


def _is_future(parsed) -> bool:
    """Check if a parsed date is in the future."""
    if parsed is None:
        return True
    kind = parsed[0]
    if kind == "full":
        return parsed[1] >= TODAY
    elif kind == "month":
        y, m = parsed[1], parsed[2]
        return y > TODAY.year or (y == TODAY.year and m >= TODAY.month)
    elif kind == "year":
        return parsed[1] >= TODAY.year
    return True


def _date_is_valid(date_str) -> bool:
    if not isinstance(date_str, str):
        return True
    return _is_future(_parse_date_to_date(date_str))


def _filter_old_entries(entries: list[dict], date_fields: list[str]) -> list[dict]:
    def _keep(entry):
        has_future = False
        has_parsed = False
        for f in date_fields:
            val = entry.get(f, "")
            if isinstance(val, str) and val.strip():
                parsed = _parse_date_to_date(val)
                if parsed is not None:
                    has_parsed = True
                    if _is_future(parsed):
                        has_future = True
        return has_future or not has_parsed

    return [e for e in entries if _keep(e)]


_LOCAL_KEYWORDS = [
    "nice",
    "sophia",
    "antipolis",
    "cannes",
    "antibes",
    "monaco",
    "grasse",
    "alpes-maritimes",
    "alpes maritimes",
    "côte d'azur",
    "cote d'azur",
    "côte d azur",
    "cote d azur",
    "paca",
    "provence-alpes",
    "var",
    "menton",
    "saint-laurent-du-var",
    "06",
    "83",
]


def _is_local(text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    tl = text.lower()
    return any(kw in tl for kw in _LOCAL_KEYWORDS)


def _filter_local(entries: list) -> list:
    kept = []
    removed = 0
    for e in entries:
        if hasattr(e, "nom"):
            lieu = e.lieu or ""
            nom = e.nom or ""
            desc = e.description or ""
            url = e.url or ""
        else:
            lieu = e.get("lieu", "") or ""
            nom = e.get("nom", "") or ""
            desc = e.get("description", "") or ""
            url = e.get("url", "") or ""
        if lieu.strip():
            if _is_local(lieu) or _is_local(nom) or _is_local(desc):
                kept.append(e)
            else:
                removed += 1
        else:
            kept.append(e)
    if removed:
        print(
            f"      Filtre local: {removed} retires (hors zone Alpes-Maritimes/Monaco)"
        )
    return kept


_OFF_TOPIC_KEYWORDS = [
    "immobilier",
    "urbanisme",
    "construction",
    "bâtiment",
    "architecture",
    "médecine",
    "médical",
    "santé",
    "foetale",
    "hospitalier",
    "spatial",
    "espace",
    "astronomie",
    "astronautique",
    "assurance",
    "banque",
    "finance",
    "comptabilité",
]

_OFF_TOPIC_THEMATIQUES = {
    "immobilier",
    "urbanisme",
    "médecine",
    "santé",
    "espace",
    "finance",
    "assurance",
    "banque",
}

_GENERIC_NON_EVENT_KEYWORDS = [
    "calendrier des salons",
    "all cfps for",
    "appel à candidatures",
    "mairie de",
    "site web",
    "page d'accueil",
]

_EDUC_IA_KEYWORDS = {
    "ia",
    "intelligence artificielle",
    "education",
    "éducation",
    "edtech",
    "enseignement",
    "apprentissage",
    "pédagogie",
    "pédagogique",
    "formation",
    "scolaire",
    "étudiant",
    "etudiant",
    "université",
    "numerique",
    "numérique",
    "innovation",
    "tutorat",
    "concours",
    "startup",
}


def _filter_relevant_topics(entries: list, mode: str = "evenement") -> list:
    kept = []
    removed = 0
    for entry in entries:
        nom = (entry.nom or "").lower()
        desc = (entry.description or "").lower()
        thematiques = [
            t.lower() for t in (entry.thematiques or []) if isinstance(t, str)
        ]
        score = entry.score_strategique or 0
        strategique = (entry.strategique or "").lower()
        lieu = (entry.lieu or "").lower()

        if any(kw in nom for kw in _GENERIC_NON_EVENT_KEYWORDS):
            removed += 1
            continue

        if strategique == "oui" or score >= 5:
            kept.append(entry)
            continue

        has_edu_ia = any(
            any(ekw in t for ekw in _EDUC_IA_KEYWORDS) for t in thematiques
        ) or any(ekw in desc for ekw in _EDUC_IA_KEYWORDS)

        if thematiques:
            all_off_topic = all(t in _OFF_TOPIC_THEMATIQUES for t in thematiques)
            if all_off_topic and not has_edu_ia:
                removed += 1
                continue

        if (
            any(kw in desc for kw in _OFF_TOPIC_KEYWORDS)
            or any(kw in nom for kw in _OFF_TOPIC_KEYWORDS)
        ) and not has_edu_ia:
            removed += 1
            continue

        has_local = _is_local(lieu) or _is_local(nom) or _is_local(desc)
        if not has_local and score < 3:
            removed += 1
            continue

        kept.append(entry)

    if removed:
        print(f"      Filtre thematique: {removed} {mode}(s) retire(s) (hors-sujet)")
    return kept


def _fill_empty_scores(entries: list) -> list:
    for entry in entries:
        score = entry.score_strategique or 0
        if score > 0 and not entry.raison:
            themas = [
                t.lower() for t in (entry.thematiques or []) if isinstance(t, str)
            ]
            if "ia" in themas:
                entry.raison = f"Pertinent pour TUT'TOP (score {score})"
            elif any(
                t in themas
                for t in ("éducation", "education", "edtech", "enseignement")
            ):
                entry.raison = (
                    f"Evenement educatif pertinent pour TUT'TOP (score {score})"
                )
            else:
                entry.raison = f"Evenement potentiellement interessant pour TUT'TOP (score {score})"
    return entries


def _deduplicate_events(hackathons: list, evenements: list) -> tuple:
    from difflib import SequenceMatcher

    def _normalize(s):
        return (
            s.lower()
            .replace("é", "e")
            .replace("è", "e")
            .replace("ê", "e")
            .replace("à", "a")
            .replace("ù", "u")
            .replace("ç", "c")
            .replace("'", " ")
            .replace("-", " ")
            .strip()
        )

    def _similar(a, b):
        return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()

    unique_h = []
    for h in hackathons:
        if not any(_similar(h.nom, existing.nom) > 0.8 for existing in unique_h):
            unique_h.append(h)

    unique_e = []
    for e in evenements:
        if not any(_similar(e.nom, existing.nom) > 0.8 for existing in unique_e):
            unique_e.append(e)

    removed_h = len(hackathons) - len(unique_h)
    removed_e = len(evenements) - len(unique_e)
    if removed_h or removed_e:
        print(f"      Dedup: {removed_h} hackathons, {removed_e} evenements retires")

    return unique_h, unique_e


def _parse_json_from_llm(text: str) -> dict:
    import json, re

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


def extract_and_store(state: VeilleState) -> dict:
    store = dict(state.get("store", {}))
    tavily_data = store.get("tavily_data", [])
    duckduckgo_data = store.get("duckduckgo_data", [])
    raw_data = tavily_data + duckduckgo_data
    store["raw_data"] = raw_data
    hackathons = list(state.get("hackathons", []))
    evenements = list(state.get("evenements", []))

    print(
        f"\n  [EXTRACTION] Analyse de {len(raw_data)} entrees (tavily={len(tavily_data)}, duckduckgo={len(duckduckgo_data)})"
    )

    if not raw_data:
        print("    Aucune donnee a analyser")
        return {"hackathons": hackathons, "evenements": evenements}

    chunks = _chunk_data(raw_data, 4)

    for chunk in chunks:
        textes = []
        for item in chunk:
            q = item.get("query", "")
            textes.append(
                f"- {item.get('title', '')} | {item.get('url', '')} | Query: {q}"
            )

        content = "\n\n---\n\n".join(textes)

        criteria = """
Critères de score strategique (0-10) :
- Localisation : Alpes-Maritimes / Nice / Sophia / Monaco / Cannes / Antibes = 10 (MAXIMUM)
  Autre France = 1, Hors France = 0
- Pertinence TUT'TOP : correspondance directe avec les fonctionnalites TUT'TOP
  (tutorat IA, chatbot sur les cours, quiz, flashcards, correction, anti-triche, CRM scolaire,
  automatisation documents, admissions) = 10, Partielle = 5, Faible = 1
- Dates : precises et a venir = 10, approximatives = 5, pas de date = 2
- Qualite infos : nom + lieu + date + description = 10, partiel = 5
- Potentiel TUT'TOP : opportunite de demo/partenariat/presentation = 10,
  simple presence/networking = 5, faible interet = 1
"""

        TUTTOP_DESC = """
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

        PROMPT = (
            """Tu es un assistant qui extrait des hackathons et evenements EdTech depuis des pages web.

REGLE IMPORTANTE : Ne retourne que des evenements avec des dates en 2026 ou apres.
IGNORE ceux avec des dates en 2025, 2024, 2023 ou plus anciennes.
Si la date n'est pas explicite, utilise le contexte de la requete de recherche (marquee 'Query:') pour deduire l'annee.
Exemple : si la Query contient '2026', mets la date au format 'JJ/MM/AAAA' avec l'annee 2026.
Si tu n'as absolument aucune information sur la date, inclus-le mais mets la date vide.

Contexte TUT'TOP :
"""
            + TUTTOP_DESC
            + """
Quand tu rediges la description et la raison, montre comment TUT'TOP peut apporter sa solution.
Exemple raison : "TUT'TOP peut y presenter son chatbot de tutorat IA et son CRM scolaire aux etablissements de la region Paca"
Exemple pertinence_tuttop : "Opportunite de demo du chatbot et de la correction intelligente aupres des lycees de Nice"

Retourne UNIQUEMENT un JSON valide (sans markdown, sans backticks) avec cette structure exacte:
{
  "hackathons": [
    {
      "nom": "string",
      "date_debut": "JJ/MM/AAAA ou chaine vide",
      "date_fin": "JJ/MM/AAAA ou chaine vide",
      "lieu": "Ville, Pays",
      "description": "string",
      "conditions": "critères de participation (équipe, niveau, prix)",
      "url": "string",
      "type": "Hackathon/Conference/Salon/Competition",
      "thematiques": ["IA", "education", ...],
      "strategique": "Oui/Non",
      "score_strategique": 0,
      "raison": "courte explication montrant la pertinence pour TUT'TOP",
      "source": "URL de la page source",
      "pertinence_tuttop": "phrase expliquant comment TUT'TOP peut tirer parti de cet evenement"
    }
  ],
  "evenements": [
    {
      "nom": "string",
      "type": "Conference/Salon/Webinar/Competition/Summer School",
      "date": "JJ/MM/AAAA",
      "lieu": "Ville, Pays",
      "description": "string",
      "url": "string",
      "thematiques": ["IA", "education", ...],
      "strategique": "Oui/Non",
      "score_strategique": 0,
      "raison": "courte explication montrant la pertinence pour TUT'TOP",
      "source": "URL de la page source",
      "pertinence_tuttop": "phrase expliquant comment TUT'TOP peut tirer parti de cet evenement"
    }
  ]
}
"""
            + criteria
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

            for h_data in _filter_old_entries(
                data.get("hackathons", []), ["date_debut", "date_fin"]
            ):
                h = Hackathon(
                    **{k: v for k, v in h_data.items() if k in Hackathon.model_fields}
                )
                if h.nom and not any(
                    ex.nom.lower() == h.nom.lower() for ex in hackathons
                ):
                    hackathons.append(h)

            for e_data in _filter_old_entries(data.get("evenements", []), ["date"]):
                e = Evenement(
                    **{k: v for k, v in e_data.items() if k in Evenement.model_fields}
                )
                if e.nom and not any(
                    ex.nom.lower() == e.nom.lower() for ex in evenements
                ):
                    evenements.append(e)

            print(
                f"    Extrait: {len(data.get('hackathons', []))} hackathons, {len(data.get('evenements', []))} evenements"
            )

        except Exception as ex:
            print(f"    Erreur extraction: {ex}")
            continue

    hackathons = [
        h for h in hackathons if h.nom and h.nom.lower() not in ("string", "")
    ]
    evenements = [
        e for e in evenements if e.nom and e.nom.lower() not in ("string", "")
    ]
    hackathons = [h for h in hackathons if "jj/mm" not in h.date_debut.lower()]
    evenements = [e for e in evenements if "jj/mm" not in e.date.lower()]

    hackathons = _filter_local(hackathons)
    evenements = _filter_local(evenements)
    hackathons = _filter_relevant_topics(hackathons, "hackathon")
    evenements = _filter_relevant_topics(evenements, "evenement")
    hackathons = _fill_empty_scores(hackathons)
    evenements = _fill_empty_scores(evenements)
    hackathons, evenements = _deduplicate_events(hackathons, evenements)

    ddg_urls = {r["url"] for r in duckduckgo_data if r.get("url")}
    for h in hackathons:
        if h.url in ddg_urls:
            h.source_engine = "duckduckgo"
    for e in evenements:
        if e.url in ddg_urls:
            e.source_engine = "duckduckgo"

    store["raw_data"] = []
    print(f"  Total: {len(hackathons)} hackathons, {len(evenements)} evenements")

    return {"hackathons": hackathons, "evenements": evenements, "store": store}


def decide_next_veille(state: VeilleState) -> str:
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 5)
    hackathons = state.get("hackathons", [])
    evenements = state.get("evenements", [])
    total = len(hackathons) + len(evenements)

    print(
        f"\n  [DECISION] Iteration {iteration + 1}/{max_iter}, total: {total} evenements"
    )

    if iteration + 1 >= max_iter:
        print("    -> FIN: iteration max atteinte")
        return "end"

    print("    -> CONTINUER: nouvelle iteration")
    return "continue"


def _chunk_data(data: list, size: int):
    return [data[i : i + size] for i in range(0, len(data), size)]
