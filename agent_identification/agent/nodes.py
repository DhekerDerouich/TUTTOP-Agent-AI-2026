from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages
from models import Prospect
from tools.prospect_search import search_french_schools, search_tunisian_schools
from tools.api_collector import collect_from_api as api_collect
from core.deduplicator import deduplicate


class AgentState(TypedDict):
    messages: Annotated[Sequence[dict], add_messages]
    prospects: list[Prospect]
    current_index: int
    total_count: int
    pays: str
    statut: str
    limit: int
    mode: str


def _should_run(state: AgentState, mode: str) -> bool:
    requested = state.get("mode", "all")
    if requested == "all":
        return True
    return requested == mode


def find_prospects_csv(state: AgentState) -> dict:
    if not _should_run(state, "csv"):
        return {}

    pays = state.get("pays", "france")
    statut = state.get("statut", None)

    print(f"\n{'=' * 50}")
    print(f"  [CSV] Recherche dans les bases locales")
    print(f"  Pays: {pays} | Statut: {statut}")
    print(f"{'=' * 50}")

    if pays.lower() == "france":
        results = search_french_schools(statut=statut)
    elif pays.lower() == "tunisie":
        results = search_tunisian_schools(statut=statut)
    else:
        print(f"  -> Pas de source CSV pour {pays}")
        results = []

    if results and "error" not in results[0]:
        prospects = [Prospect(**r) if isinstance(r, dict) else r for r in results]
    else:
        prospects = []

    print(f"  -> {len(prospects)} prospects trouves dans les CSV")

    existing = list(state.get("prospects", []))
    all_prospects = deduplicate(existing + prospects)

    return {
        "prospects": all_prospects,
        "total_count": len(all_prospects),
    }


def find_prospects_api(state: AgentState) -> dict:
    if not _should_run(state, "api"):
        return {}

    statut = state.get("statut", None)
    pays = state.get("pays", "france")

    print(f"\n{'=' * 50}")
    print(f"  [API] Collecte via APIs officielles")
    print(f"  Pays: {pays} | Statut: {statut}")
    print(f"{'=' * 50}")

    results = api_collect(statut=statut, pays=pays)

    if results and "error" not in results[0]:
        prospects = [Prospect(**r) if isinstance(r, dict) else r for r in results]
    else:
        prospects = []

    print(f"  -> {len(prospects)} prospects trouves via API")

    existing = list(state.get("prospects", []))
    all_prospects = deduplicate(existing + prospects)

    return {
        "prospects": all_prospects,
        "total_count": len(all_prospects),
    }


def find_prospects_web(state: AgentState) -> dict:
    if not _should_run(state, "web"):
        return {}

    statut = state.get("statut", None)
    pays = state.get("pays", "france")

    print(f"\n{'=' * 50}")
    print(f"  [WEB] Recherche autonome sur le web")
    print(f"  Pays: {pays} | Statut: {statut}")
    print(f"{'=' * 50}")

    from tools.web_collector import collect_from_web

    pays_label = {
        "france": "France",
        "belgique": "Belgique",
        "suisse": "Suisse",
        "tunisie": "Tunisie",
    }.get(pays.lower(), "France")
    results = collect_from_web(statut=statut, pays=pays_label)

    if results and "error" not in results[0]:
        prospects = [Prospect(**r) if isinstance(r, dict) else r for r in results]
    else:
        prospects = []

    print(f"  -> {len(prospects)} prospects trouves via le web")

    existing = list(state.get("prospects", []))
    all_prospects = deduplicate(existing + prospects)

    return {
        "prospects": all_prospects,
        "total_count": len(all_prospects),
    }
