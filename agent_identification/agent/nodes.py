from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages
from models import Prospect
from tools.prospect_search import search_french_schools, search_tunisian_schools


class AgentState(TypedDict):
    messages: Annotated[Sequence[dict], add_messages]
    prospects: list[Prospect]
    current_index: int
    total_count: int
    pays: str
    statut: str
    limit: int


def find_prospects(state: AgentState) -> dict:
    pays = state.get("pays", "france")
    statut = state.get("statut", None)
    limit = state.get("limit", 50)

    print(f"\n{'=' * 50}")
    print(f"  RECHERCHE DE PROSPECTS")
    print(f"  Pays: {pays} | Statut: {statut} | Limit: {limit}")
    print(f"{'=' * 50}")

    if pays.lower() == "tunisie":
        results = search_tunisian_schools(statut=statut, limit=limit)
    else:
        results = search_french_schools(statut=statut, limit=limit)

    if results and "error" not in results[0]:
        prospects = [Prospect(**r) if isinstance(r, dict) else r for r in results]
    else:
        prospects = []

    print(f"  -> {len(prospects)} prospects trouves")
    for p in prospects:
        site = p.site_web or "NON"
        print(f"    - {p.nom} ({p.type.value}) | {p.localisation} | site: {site}")

    return {
        "prospects": prospects,
        "current_index": 0,
        "total_count": len(prospects),
    }


def should_continue(state: AgentState) -> str:
    if state["current_index"] >= state["total_count"]:
        return "finish"
    return "continue"
