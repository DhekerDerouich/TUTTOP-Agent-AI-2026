import sys
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "false")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from agent.veille_graph import agent as veille_agent
from agent.veille_nodes import VeilleState


def run_veille(
    max_iterations: int = 5,
    thread_id: str = "veille-1",
) -> dict:
    initial_state: VeilleState = {
        "messages": [],
        "hackathons": [],
        "evenements": [],
        "queries_executees": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "store": {
            "raw_data": [],
        },
    }

    config = {"configurable": {"thread_id": thread_id}}

    graph = veille_agent
    for event in graph.stream(initial_state, config):
        for node_name, values in event.items():
            if "iteration" in values and values["iteration"] != initial_state.get(
                "iteration", 0
            ):
                pass

    final_state = graph.get_state(config)
    return final_state.values


def export_results(
    hackathons: list,
    evenements: list,
    prefix: str = "data/veille",
):
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    hack_data = []
    for h in hackathons:
        if hasattr(h, "model_dump"):
            hack_data.append(h.model_dump())
        else:
            hack_data.append(dict(h))

    event_data = []
    for e in evenements:
        if hasattr(e, "model_dump"):
            event_data.append(e.model_dump())
        else:
            event_data.append(dict(e))

    csv_hack = out_dir / f"{prefix}_hackathons.csv"
    csv_event = out_dir / f"{prefix}_evenements.csv"
    xlsx_path = out_dir / f"{prefix}.xlsx"

    if hack_data:
        df_h = pd.DataFrame(hack_data)
        df_h.to_csv(csv_hack, index=False, encoding="utf-8-sig")
        print(f"  -> {len(hack_data)} hackathons exportes: {csv_hack}")
    else:
        pd.DataFrame().to_csv(csv_hack, index=False, encoding="utf-8-sig")
        print(f"  -> 0 hackathons (fichier vide cree)")

    if event_data:
        df_e = pd.DataFrame(event_data)
        df_e.to_csv(csv_event, index=False, encoding="utf-8-sig")
        print(f"  -> {len(event_data)} evenements exportes: {csv_event}")
    else:
        pd.DataFrame().to_csv(csv_event, index=False, encoding="utf-8-sig")
        print(f"  -> 0 evenements (fichier vide cree)")

    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            if hack_data:
                pd.DataFrame(hack_data).to_excel(
                    writer, sheet_name="Hackathons", index=False
                )
            else:
                pd.DataFrame().to_excel(writer, sheet_name="Hackathons", index=False)
            if event_data:
                pd.DataFrame(event_data).to_excel(
                    writer, sheet_name="Evenements", index=False
                )
            else:
                pd.DataFrame().to_excel(writer, sheet_name="Evenements", index=False)
        print(f"  -> Fichier Excel complete: {xlsx_path}")
    except PermissionError:
        print(f"  -> Impossible d'ecrire {xlsx_path} (fichier ouvert?)")
    except Exception as ex:
        print(f"  -> Erreur export Excel: {ex}")

    return {
        "csv_hack": str(csv_hack),
        "csv_event": str(csv_event),
        "xlsx": str(xlsx_path),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent de veille Hackathons & Evenements TUT'TOP"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Nombre maximum d'iterations de recherche (defaut: 5)",
    )
    parser.add_argument(
        "--thread-id",
        default="veille-1",
        help="ID de thread pour le checkpointer",
    )
    parser.add_argument(
        "--output-prefix",
        default="veille",
        help="Prefixe des fichiers de sortie (dans data/)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Filtrer les resultats avec score strategique >= N (0-10)",
    )
    args = parser.parse_args()

    print(f"\n=== Agent de veille Hackathons & Evenements TUT'TOP ===")
    print(f"  Iterations max: {args.max_iterations}")
    print(f"  Thread ID: {args.thread_id}")
    print(f"  Output prefix: {args.output_prefix}")
    print()

    results = run_veille(
        max_iterations=args.max_iterations,
        thread_id=args.thread_id,
    )

    hackathons = results.get("hackathons", [])
    evenements = results.get("evenements", [])

    min_score = args.min_score
    if min_score > 0:
        hackathons = [
            h
            for h in hackathons
            if (
                h.score_strategique
                if hasattr(h, "score_strategique")
                else h.get("score_strategique", 0)
            )
            >= min_score
        ]
        evenements = [
            e
            for e in evenements
            if (
                e.score_strategique
                if hasattr(e, "score_strategique")
                else e.get("score_strategique", 0)
            )
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
            s = (
                h.score_strategique
                if hasattr(h, "score_strategique")
                else h.get("score_strategique", 0)
            )
            nom = h.nom if hasattr(h, "nom") else h.get("nom", "")
            lieu = h.lieu if hasattr(h, "lieu") else h.get("lieu", "")
            raison = h.raison if hasattr(h, "raison") else h.get("raison", "")
            scored.append((s, nom, lieu, raison))
        for s, nom, lieu, raison in sorted(scored, reverse=True):
            r = f" | {raison}" if raison else ""
            print(f"  [{s}/10] {nom} | {lieu}{r}")

    if evenements:
        print(f"\nEvenements tries par score strategique:")
        scored = []
        for e in evenements:
            s = (
                e.score_strategique
                if hasattr(e, "score_strategique")
                else e.get("score_strategique", 0)
            )
            nom = e.nom if hasattr(e, "nom") else e.get("nom", "")
            lieu = e.lieu if hasattr(e, "lieu") else e.get("lieu", "")
            type_e = e.type if hasattr(e, "type") else ""
            raison = e.raison if hasattr(e, "raison") else e.get("raison", "")
            scored.append((s, nom, lieu, type_e, raison))
        for s, nom, lieu, type_e, raison in sorted(scored, reverse=True):
            r = f" | {raison}" if raison else ""
            print(f"  [{s}/10] {nom} ({type_e}) | {lieu}{r}")

    export_results(hackathons, evenements, prefix=args.output_prefix)
