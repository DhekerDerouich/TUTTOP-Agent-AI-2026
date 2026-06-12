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
        "store": {
            "collected": False,
            "unknown_count": 0,
            "cleaned": False,
            "qualified": False,
        },
    }

    config = {"configurable": {"thread_id": thread_id}}
    result = collector_agent.invoke(initial_state, config)

    return result.get("prospects", [])


def run_processing(
    input_csv: str = "data/all_data.csv",
    provider: str = "groq",
    sample: int = 0,
    batch: int = 100,
    thread_id: str = "process-1",
) -> list[dict]:
    in_path = Path(__file__).parent / input_csv
    if not in_path.exists():
        print(f"Fichier introuvable: {in_path}")
        return []

    df = pd.read_csv(in_path, dtype=str, encoding="utf-8-sig")
    df = df.fillna("")
    records = df.to_dict("records")

    if sample > 0:
        records = records[:sample]
        print(f"Mode echantillon: {sample} lignes")

    print(f"Charge {len(records)} prospects depuis {input_csv}")

    from agent.classifier import classify_types
    from agent.cleaner import clean_prospects
    from agent.qualifier import qualify_prospects

    unknown = sum(1 for r in records if r.get("type") == "Inconnu")
    print(f"  Types: Inconnu={unknown}")

    records = classify_types(records, provider=provider, batch_size=batch)
    records = clean_prospects(records)
    records = qualify_prospects(records)

    return records


def export_to_csv(
    prospects: list[Prospect] | list[dict],
    filename: str = "data/prospects_bruts.csv",
):
    if prospects and hasattr(prospects[0], "model_dump"):
        data = [p.model_dump() for p in prospects]
    else:
        data = list(prospects)

    out_path = Path(__file__).parent / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(data)
    if "score" in df.columns:
        cols = [
            "nom",
            "type",
            "localisation",
            "site_web",
            "email",
            "telephone",
            "source",
            "pays",
            "score",
            "qualification",
        ]
        cols = [c for c in cols if c in df.columns]
        df = df[cols + [c for c in df.columns if c not in cols]]
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nExporte {len(data)} prospects -> {out_path}")
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent de prospection EdTech TUT'TOP")
    parser.add_argument(
        "--pays",
        default="france",
        choices=["france", "belgique", "suisse", "tunisie", "europe"],
    )
    parser.add_argument("--statut", default=None, choices=["Prive", "Privé", "Public"])
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--mode",
        default="all",
        choices=["csv", "api", "web", "all", "process"],
        help="csv=CSV, api=APIs, web=web, all=tout, process=classify+clean+qualify",
    )
    parser.add_argument(
        "--provider",
        default="groq",
        choices=["groq", "openai", "gemini", "ollama"],
        help="Fournisseur LLM pour la classification (mode process)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Traiter seulement N lignes (mode process)",
    )
    parser.add_argument(
        "--batch", type=int, default=100, help="Taille des lots LLM (mode process)"
    )
    args = parser.parse_args()

    if args.mode == "process":
        print(f"\n=== Mode PROCESS : Classification + Nettoyage + Qualification ===")
        print(f"  provider={args.provider}, sample={args.sample}, batch={args.batch}\n")
        results = run_processing(
            provider=args.provider, sample=args.sample, batch=args.batch
        )
        if results:
            chaud = sum(1 for r in results if r.get("qualification") == "Chaud")
            tiede = sum(1 for r in results if r.get("qualification") == "Tiède")
            froid = sum(1 for r in results if r.get("qualification") == "Froid")
            print(f"\nResultats: Chaud={chaud}, Tiède={tiede}, Froid={froid}")
            suffix = f"_sample{args.sample}" if args.sample else "_enriched"
            export_to_csv(results, f"data/all_data{suffix}.csv")
    else:
        print(
            f"\nLancement de la collecte : {args.pays}, statut={args.statut}, mode={args.mode}"
        )
        if args.mode in ("csv", "api"):
            print("  (collecte integrale - sans limite de nombre)")
        else:
            print(f"  (limite web: {args.limit})")
        prospects = run_collector(
            pays=args.pays, statut=args.statut, limit=args.limit, mode=args.mode
        )

        labels = {
            "csv": "CSV",
            "api": "API",
            "web": "recherche web",
            "all": "CSV + API + Web",
        }
        print(
            f"\n[{args.mode.upper()}] Resultats : {len(prospects)} prospects collectes via {labels.get(args.mode, '')}"
        )

        for p in prospects:
            site = p.site_web or "NON"
            print(
                f"  - {p.nom} ({p.type.value}) | {p.localisation} | site: {site} | src: {p.source}"
            )

        if prospects:
            export_to_csv(prospects, f"data/prospects_{args.mode}_{args.pays}.csv")
