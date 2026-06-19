import sys
import os
import json
import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "false")
os.environ["LANGCHAIN_PROJECT"] = "TUTTOP-agent-unified"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from agent.unified_graph import agent as unified_agent, UnifiedState
from agent.veille_models import Hackathon, Evenement

CHECKPOINT_PATH = Path(__file__).parent / "data" / "state_veille.json"


def save_checkpoint(state: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "hackathons": [
            h.model_dump() if hasattr(h, "model_dump") else h
            for h in state.get("hackathons", [])
        ],
        "evenements": [
            e.model_dump() if hasattr(e, "model_dump") else e
            for e in state.get("evenements", [])
        ],
        "queries_executees": state.get("queries_executees", []),
    }
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  [CHECKPOINT] State sauvegarde -> {CHECKPOINT_PATH}")


def load_checkpoint() -> dict:
    if not CHECKPOINT_PATH.exists():
        print(f"  [CHECKPOINT] Aucun checkpoint trouve, demarrage a zero")
        return {}
    with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = {
        "hackathons": [Hackathon(**h) for h in data.get("hackathons", [])],
        "evenements": [Evenement(**e) for e in data.get("evenements", [])],
        "queries_executees": data.get("queries_executees", []),
    }
    print(
        f"  [CHECKPOINT] Charge: {len(result['hackathons'])} hackathons, "
        f"{len(result['evenements'])} evenements, "
        f"{len(result['queries_executees'])} requetes deja executees"
    )
    return result


def run_prospection(args):
    from models import Prospect

    if args.statut and "Priv" in args.statut:
        args.statut = "Prive"

    initial_state: UnifiedState = {
        "task": "prospection",
        "messages": [],
        "store": {
            "collected": False,
            "unknown_count": 0,
            "cleaned": False,
            "qualified": False,
        },
        "prospects": [],
        "current_index": 0,
        "total_count": 0,
        "pays": args.pays,
        "statut": args.statut,
        "limit": args.limit,
        "mode": args.collect_mode,
        "hackathons": [],
        "evenements": [],
        "queries_executees": [],
        "iteration": 0,
        "max_iterations": 0,
    }

    config = {"configurable": {"thread_id": args.thread_id}}
    for event in unified_agent.stream(initial_state, config):
        pass
    result = unified_agent.get_state(config)
    prospects = result.values.get("prospects", [])

    labels = {
        "csv": "CSV",
        "api": "API",
        "web": "recherche web",
        "all": "CSV + API + Web",
    }
    print(
        f"\n[{args.collect_mode.upper()}] Resultats : {len(prospects)} prospects collectes via {labels.get(args.collect_mode, '')}"
    )

    for p in prospects:
        site = p.site_web or "NON"
        print(
            f"  - {p.nom} ({p.type.value}) | {p.localisation} | site: {site} | src: {p.source}"
        )

    if prospects:
        from main import export_to_csv

        export_to_csv(prospects, f"data/prospects_{args.collect_mode}_{args.pays}.csv")

    return prospects


def run_veille(args):
    initial_state: UnifiedState = {
        "task": "veille",
        "messages": [],
        "store": {},
        "prospects": [],
        "current_index": 0,
        "total_count": 0,
        "pays": "",
        "statut": "",
        "limit": 0,
        "mode": "",
        "hackathons": [],
        "evenements": [],
        "queries_executees": [],
        "iteration": 0,
        "max_iterations": args.max_iterations,
    }

    if args.load_checkpoint:
        ckpt = load_checkpoint()
        initial_state["hackathons"] = ckpt.get("hackathons", [])
        initial_state["evenements"] = ckpt.get("evenements", [])
        initial_state["queries_executees"] = ckpt.get("queries_executees", [])

    config = {"configurable": {"thread_id": args.thread_id}}

    for event in unified_agent.stream(initial_state, config):
        pass

    final = unified_agent.get_state(config)
    values = final.values

    hackathons = values.get("hackathons", [])
    evenements = values.get("evenements", [])

    min_score = args.min_score
    if min_score > 0:
        hackathons = [
            h
            for h in hackathons
            if (h.score_strategique if hasattr(h, "score_strategique") else 0)
            >= min_score
        ]
        evenements = [
            e
            for e in evenements
            if (e.score_strategique if hasattr(e, "score_strategique") else 0)
            >= min_score
        ]

    print(f"\n{'=' * 60}")
    print(f"  RESULTATS FINAUX")
    print(f"  Hackathons: {len(hackathons)}")
    print(f"  Evenements: {len(evenements)}")
    print(f"  Total: {len(hackathons) + len(evenements)}")
    print(f"  Score min: {min_score}")
    print(f"{'=' * 60}")

    if hackathons:
        print(f"\nHackathons tries par score strategique:")
        scored = []
        for h in hackathons:
            s = h.score_strategique if hasattr(h, "score_strategique") else 0
            nom = h.nom if hasattr(h, "nom") else ""
            lieu = h.lieu if hasattr(h, "lieu") else ""
            raison = h.raison if hasattr(h, "raison") else ""
            scored.append((s, nom, lieu, raison))
        for s, nom, lieu, raison in sorted(scored, reverse=True):
            r = f" | {raison}" if raison else ""
            print(f"  [{s}/10] {nom} | {lieu}{r}")

    if evenements:
        print(f"\nEvenements tries par score strategique:")
        scored = []
        for e in evenements:
            s = e.score_strategique if hasattr(e, "score_strategique") else 0
            nom = e.nom if hasattr(e, "nom") else ""
            lieu = e.lieu if hasattr(e, "lieu") else ""
            type_e = e.type if hasattr(e, "type") else ""
            raison = e.raison if hasattr(e, "raison") else ""
            scored.append((s, nom, lieu, type_e, raison))
        for s, nom, lieu, type_e, raison in sorted(scored, reverse=True):
            r = f" | {raison}" if raison else ""
            print(f"  [{s}/10] {nom} ({type_e}) | {lieu}{r}")

    from run_veille import export_results

    export_results(hackathons, evenements, prefix=args.output_prefix)
    export_results(
        hackathons, evenements, prefix=args.output_prefix, source_filter="tavily"
    )
    export_results(
        hackathons, evenements, prefix=args.output_prefix, source_filter="duckduckgo"
    )

    save_checkpoint(values)

    return values


def main():
    parser = argparse.ArgumentParser(
        description="Agent unifie TUT'TOP : Prospection etablissements + Veille EdTech"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["prospection", "veille"],
        help="Mode d'execution",
    )
    parser.add_argument(
        "--thread-id",
        default="unified-1",
        help="ID de thread pour le checkpointer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Teste la compilation du graphe sans execution",
    )

    sub_args, remaining = parser.parse_known_args()

    if sub_args.dry_run:
        print(f"\n=== DRY RUN: Verification du graphe unifie ===")
        print(f"  Noeuds: {list(unified_agent.get_graph().nodes.keys())}")
        edges = list(unified_agent.get_graph().edges)
        print(f"  Arets: {edges[:10]}{'...' if len(edges) > 10 else ''}")
        print(f"  Graph compile avec succes!")
        return

    if sub_args.mode == "prospection":
        p = argparse.ArgumentParser()
        p.add_argument("--pays", default="france")
        p.add_argument("--statut", default=None)
        p.add_argument("--limit", type=int, default=5000)
        p.add_argument(
            "--collect-mode",
            default="all",
            choices=["csv", "api", "web", "all"],
            help="csv=CSV, api=APIs, web=web, all=tout",
        )
        p.add_argument("--thread-id", default="unified-1")
        p.add_argument("--dry-run", action="store_true")
        args, _ = p.parse_known_args(remaining)
        args.thread_id = sub_args.thread_id
        args.dry_run = sub_args.dry_run
        run_prospection(args)

    elif sub_args.mode == "veille":
        p = argparse.ArgumentParser()
        p.add_argument("--max-iterations", type=int, default=5)
        p.add_argument("--thread-id", default="unified-1")
        p.add_argument("--output-prefix", default="veille")
        p.add_argument("--min-score", type=int, default=0)
        p.add_argument(
            "--load-checkpoint",
            action="store_true",
            help="Charger l'etat depuis data/state_veille.json",
        )
        p.add_argument("--dry-run", action="store_true")
        args, _ = p.parse_known_args(remaining)
        args.thread_id = sub_args.thread_id
        args.dry_run = sub_args.dry_run
        run_veille(args)


if __name__ == "__main__":
    main()
