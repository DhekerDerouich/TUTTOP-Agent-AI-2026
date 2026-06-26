import sys
import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "false")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ.setdefault("LANGCHAIN_PROJECT", "TUTTOP-agent-unified")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from agent.unified_graph import agent as unified_agent, UnifiedState
from agent.veille_models import Hackathon, Evenement
from agent.subventions_models import Subvention

CHECKPOINT_PATH = Path(__file__).parent / "data" / "state_veille.json"
CHECKPOINT_SUBVENTIONS_PATH = Path(__file__).parent / "data" / "state_subventions.json"


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


def save_checkpoint_subventions(state: dict):
    CHECKPOINT_SUBVENTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "subventions": [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in state.get("subventions", [])
        ],
        "queries_executees": state.get("queries_executees", []),
    }
    with open(CHECKPOINT_SUBVENTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  [CHECKPOINT] Subventions sauvegardees -> {CHECKPOINT_SUBVENTIONS_PATH}")


def load_checkpoint_subventions() -> dict:
    if not CHECKPOINT_SUBVENTIONS_PATH.exists():
        print(f"  [CHECKPOINT] Aucun checkpoint subventions trouve, demarrage a zero")
        return {}
    with open(CHECKPOINT_SUBVENTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = {
        "subventions": [Subvention(**s) for s in data.get("subventions", [])],
        "queries_executees": data.get("queries_executees", []),
    }
    print(
        f"  [CHECKPOINT] Charge: {len(result['subventions'])} subventions, "
        f"{len(result['queries_executees'])} requetes deja executees"
    )
    return result


def export_subventions(subventions: list[Subvention], prefix: str = "subventions"):
    import pandas as pd

    outdir = Path(__file__).parent / "data"
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in subventions:
        d = s.model_dump() if hasattr(s, "model_dump") else {}
        rows.append(
            {
                "Nom": d.get("nom", ""),
                "Type": d.get("type", ""),
                "Sous-type": d.get("sous_type", ""),
                "Organisme": d.get("organisme", ""),
                "Region": d.get("region", ""),
                "Public cible": d.get("public_cible", ""),
                "Deadline": d.get("deadline", ""),
                "Date publication": d.get("date_publication", ""),
                "Montant": d.get("montant", ""),
                "Eligibilite": d.get("eligibilite", ""),
                "Mots-cles": d.get("mots_cles", ""),
                "Type aide": d.get("type_aide", ""),
                "Statut": d.get("statut", ""),
                "Priorite": d.get("priorite", ""),
                "Score": d.get("score_strategique", 0),
                "Pertinence": d.get("pertinence", ""),
                "Raison": d.get("raison", ""),
                "URL": d.get("url", ""),
                "Lien officiel": d.get("lien_officiel", ""),
                "Derniere verification": d.get("date_derniere_verification", ""),
            }
        )

    df_new = pd.DataFrame(rows)
    path = outdir / f"{prefix}_all.xlsx"

    if path.exists():
        df_old = pd.read_excel(path, dtype=str, engine="openpyxl").fillna("")
        df_new = pd.concat([df_old, df_new], ignore_index=True)
        dedup_col = "Nom"
        if dedup_col in df_new.columns:
            df_new = df_new.drop_duplicates(subset=[dedup_col], keep="last")
        print(
            f"  Merge: {len(df_old)} existantes + {len(rows)} nouvelles = {len(df_new)} total"
        )

    df_new.to_excel(path, index=False, engine="openpyxl")
    print(f"  Exporte {len(df_new)} subventions -> {path}")


def run_prospection(args):
    from models import Prospect

    if args.statut and "Priv" in args.statut:
        args.statut = "Privé"

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
        "mode": "csv" if getattr(args, "quick", False) else "all",
        "hackathons": [],
        "evenements": [],
        "queries_executees": [],
        "iteration": 0,
        "max_iterations": 0,
        "subventions": [],
        "subventions_iteration": 0,
        "subventions_max_iterations": 0,
    }

    config = {"configurable": {"thread_id": args.thread_id}}
    for event in unified_agent.stream(initial_state, config, stream_mode="updates"):
        pass
    result = unified_agent.get_state(config)
    prospects = result.values.get("prospects", [])

    print(
        f"\n[PROSPECTION] Resultats : {len(prospects)} prospects collectes (CSV + API + Web)"
    )

    for p in prospects:
        site = p.site_web or "NON"
        print(
            f"  - {p.nom} ({p.type.value}) | {p.localisation} | site: {site} | src: {p.source}"
        )

    if prospects:
        from main import export_to_csv

        export_to_csv(prospects, f"data/prospects_all_{args.pays}.csv")

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
        "subventions": [],
        "subventions_iteration": 0,
        "subventions_max_iterations": 0,
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


def run_subventions(args):
    initial_state: UnifiedState = {
        "task": "subventions",
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
        "max_iterations": 0,
        "subventions": [],
        "subventions_iteration": 0,
        "subventions_max_iterations": args.subventions_max_iterations,
    }

    if args.load_checkpoint:
        ckpt = load_checkpoint_subventions()
        initial_state["subventions"] = ckpt.get("subventions", [])
        initial_state["queries_executees"] = ckpt.get("queries_executees", [])

    config = {"configurable": {"thread_id": args.thread_id}}

    for event in unified_agent.stream(initial_state, config):
        pass

    final = unified_agent.get_state(config)
    values = final.values

    subventions = values.get("subventions", [])

    min_score = args.min_score
    if min_score > 0:
        subventions = [
            s
            for s in subventions
            if (s.score_strategique if hasattr(s, "score_strategique") else 0)
            >= min_score
        ]

    print(f"\n{'=' * 60}")
    print(f"  RESULTATS SUBVENTIONS")
    print(f"  Total: {len(subventions)} aides/subventions trouvees")
    print(f"  Score min: {min_score}")
    print(f"{'=' * 60}")

    if subventions:
        print(f"\nSubventions triees par score strategique:")
        scored = []
        for s in subventions:
            sc = s.score_strategique if hasattr(s, "score_strategique") else 0
            nom = s.nom if hasattr(s, "nom") else ""
            org = s.organisme if hasattr(s, "organisme") else ""
            priorite = s.priorite if hasattr(s, "priorite") and s.priorite else ""
            statut = s.statut if hasattr(s, "statut") and s.statut else ""
            type_aide = s.type_aide if hasattr(s, "type_aide") and s.type_aide else ""
            scored.append((sc, nom, org, priorite, statut, type_aide))
        for sc, nom, org, priorite, statut, type_aide in sorted(scored, reverse=True):
            p = f" [{priorite}]" if priorite else ""
            st = f" ({statut})" if statut else ""
            ta = f" {type_aide}" if type_aide else ""
            print(f"  [{sc}/10]{p} {nom} ({org}){st}{ta}")

    export_subventions(subventions, prefix="subventions")
    save_checkpoint_subventions(values)

    return values


def main():
    parser = argparse.ArgumentParser(
        description="Agent unifie TUT'TOP : Prospection etablissements + Veille EdTech + Subventions"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["prospection", "veille", "subventions", "all"],
        help="Mode d'execution (prospection, veille, subventions, ou all pour tout)",
    )
    parser.add_argument("--thread-id", default="unified-1")
    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--pays", default="france")
    parser.add_argument("--statut", default=None)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Mode rapide: CSV + processing uniquement (skip API/Web)",
    )
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--subventions-max-iterations", type=int, default=5)
    parser.add_argument("--output-prefix", default="veille")
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--load-checkpoint", action="store_true")

    args = parser.parse_args()

    if args.dry_run:
        print(f"\n=== DRY RUN: Verification du graphe unifie ===")
        print(f"  Noeuds: {list(unified_agent.get_graph().nodes.keys())}")
        edges = list(unified_agent.get_graph().edges)
        print(f"  Arets: {edges[:10]}{'...' if len(edges) > 10 else ''}")
        print(f"  Graph compile avec succes!")
        return

    if args.mode == "prospection":
        run_prospection(args)

    elif args.mode == "veille":
        run_veille(args)

    elif args.mode == "subventions":
        run_subventions(args)

    elif args.mode == "all":
        print("\n" + "=" * 60)
        print("  PHASE 1/3 : PROSPECTION")
        print("=" * 60)
        run_prospection(args)

        print("\n" + "=" * 60)
        print("  PHASE 2/3 : VEILLE EVENEMENTIELLE")
        print("=" * 60)
        run_veille(args)

        print("\n" + "=" * 60)
        print("  PHASE 3/3 : SUBVENTIONS & FINANCEMENTS")
        print("=" * 60)
        run_subventions(args)

        print("\n" + "=" * 60)
        print("  PIPELINE COMPLET TERMINE")
        print("=" * 60)


if __name__ == "__main__":
    main()
