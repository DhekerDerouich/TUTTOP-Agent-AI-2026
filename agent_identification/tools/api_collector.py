import requests
import json
from pathlib import Path
from core.extractor import normalize_prospect


def load_sources() -> list[dict]:
    path = Path(__file__).parent.parent / "config" / "sources.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sources", [])


def collect_from_api(statut: str | None = None, limit: int = 50) -> list[dict]:
    sources = load_sources()
    api_sources = [
        s for s in sources if s.get("type") == "api" and s.get("enabled", True)
    ]

    all_results = []
    for source in api_sources:
        pays = source["pays"]
        url = source["url"]
        mapping = source.get("mapping", {})
        params = dict(source.get("params", {}))
        params["limit"] = min(limit, 100)

        where_clauses = ["web is not null"]
        if statut:
            if "Priv" in statut:
                where_clauses.append(
                    f"{mapping.get('type', 'statut_public_prive')} = 'Priv\u00e9'"
                )
            else:
                where_clauses.append(
                    f"{mapping.get('type', 'statut_public_prive')} = 'Public'"
                )

        if where_clauses:
            params["where"] = " AND ".join(where_clauses)

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("results", data.get("records", []))
            print(f"    Total count: {data.get('total_count', '?')}")
        except Exception as e:
            print(f"  Erreur API {pays}: {e}")
            continue

        for item in records:
            raw = {}
            for target_field, source_field in mapping.items():
                val = item.get(source_field)
                if val is None:
                    val = item.get(f"fields.{source_field}")
                raw[target_field] = val

            raw["departement"] = item.get(mapping.get("departement", ""), "")
            prospect = normalize_prospect(raw, pays, f"api_{source['id']}")
            all_results.append(prospect)

        print(f"  API {pays}: {len(records)} trouves")

    return all_results
