import sys
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from agent.graph import agent as collector_agent
from agent.nodes import AgentState
from models import Prospect


def run_collector(
    pays: str = "france",
    statut: str | None = None,
    limit: int = 50,
    thread_id: str = "collecte-1",
) -> list[Prospect]:
    if statut and "Priv" in statut:
        statut = "Privé"
    initial_state: AgentState = {
        "messages": [],
        "prospects": [],
        "current_index": 0,
        "total_count": 0,
        "pays": pays,
        "statut": statut,
        "limit": limit,
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = collector_agent.invoke(initial_state, config)

    return result.get("prospects", [])


def export_to_csv(
    prospects: list[Prospect], filename: str = "data/prospects_bruts.csv"
):
    data = [p.model_dump() for p in prospects]

    out_path = Path(__file__).parent / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(data)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nExporte {len(data)} prospects -> {out_path}")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent de collecte EdTech TUT'TOP")
    parser.add_argument("--pays", default="france", choices=["france", "tunisie"])
    parser.add_argument("--statut", default=None, choices=["Prive", "Privé", "Public"])
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    print(
        f"Lancement de la collecte : {args.pays}, statut={args.statut}, limit={args.limit}"
    )
    prospects = run_collector(pays=args.pays, statut=args.statut, limit=args.limit)

    print(f"\nResultats : {len(prospects)} prospects collectes")
    for p in prospects:
        site = p.site_web or "NON"
        print(f"  - {p.nom} ({p.type.value}) | {p.localisation} | site: {site}")

    if prospects:
        export_to_csv(prospects)
