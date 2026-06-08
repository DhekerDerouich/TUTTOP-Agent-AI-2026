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
    limit: int = 5000,
    mode: str = "all",
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
        "mode": mode,
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
    parser.add_argument(
        "--pays", default="france", choices=["france", "belgique", "suisse", "tunisie"]
    )
    parser.add_argument("--statut", default=None, choices=["Prive", "Privé", "Public"])
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--mode",
        default="all",
        choices=["csv", "api", "web", "all"],
        help="csv=CSV locaux, api=APIs officielles, web=recherche web, all=tout",
    )
    args = parser.parse_args()

    print(
        f"\nLancement de la collecte : {args.pays}, statut={args.statut}, mode={args.mode}"
    )
    if args.mode in ("csv", "api"):
        print(f"  (collecte integrale - sans limite de nombre)")
    else:
        print(f"  (limite web: {args.limit})")
    prospects = run_collector(
        pays=args.pays, statut=args.statut, limit=args.limit, mode=args.mode
    )

    if args.mode == "csv":
        print(f"\n[CSV] Resultats : {len(prospects)} prospects collectes")
    elif args.mode == "api":
        print(f"\n[API] Resultats : {len(prospects)} prospects collectes via API")
    elif args.mode == "web":
        print(f"\n[WEB] Resultats : {len(prospects)} prospects collectes via le web")
    else:
        print(
            f"\n[ALL] Resultats : {len(prospects)} prospects collectes (CSV + API + Web)"
        )

    for p in prospects:
        site = p.site_web or "NON"
        print(
            f"  - {p.nom} ({p.type.value}) | {p.localisation} | site: {site} | src: {p.source}"
        )

    if prospects:
        export_to_csv(prospects, f"data/prospects_{args.mode}_{args.pays}.csv")
