from langchain_core.messages import HumanMessage
from agent.llm import get_llm

PLAN_PROMPT = """Tu es l'orchestrateur de l'agent de prospection EdTech TUT'TOP.
Analyse l'etat actuel et decide la prochaine action.

Etat actuel :
- prospects_collectes: {collected}
- types_inconnus: {unknown}
- cleaned: {cleaned}
- qualified: {qualified}

Actions disponibles :
- classify : lancer la classification des types "Inconnu" via LLM
- clean : nettoyer et dedupliquer les donnees
- qualify : scorer et qualifier les prospects (Chaud/Tiede/Froid)
- done : toutes les etapes sont terminees

Reponds UNIQUEMENT avec le nom de l'action."""


def orchestrator(state: dict) -> dict:
    store = state.get("store", {})
    unknown = store.get("unknown_count", 0)
    cleaned = store.get("cleaned", False)
    qualified = store.get("qualified", False)
    collected = store.get("collected", False)

    if not collected:
        return {"next_action": "collect"}

    if not unknown and cleaned and qualified:
        return {"next_action": "done"}

    prompt = PLAN_PROMPT.format(
        collected=collected,
        unknown=unknown,
        cleaned=cleaned,
        qualified=qualified,
    )

    try:
        llm = get_llm(provider="groq")
        msg = llm.invoke([HumanMessage(content=prompt)])
        action = msg.content.strip().lower()
        if action in ("classify", "clean", "qualify", "done"):
            print(f"  [LLM Orchestrator] decide -> {action}")
            return {"next_action": action}
    except Exception as e:
        print(f"  [LLM Orchestrator] erreur, fallback logique: {e}")

    if unknown > 0 and not cleaned:
        return {"next_action": "classify"}
    if cleaned and not qualified:
        return {"next_action": "qualify"}
    if not cleaned:
        return {"next_action": "clean"}
    return {"next_action": "done"}
