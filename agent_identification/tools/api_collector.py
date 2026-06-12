import requests
import json
import time
import io
import threading
import pandas as pd
from pathlib import Path
from core.extractor import normalize_prospect

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TUTTOP-Agent/1.0"

ISO_TO_COUNTRY = {
    "FR": "France",
    "BE": "Belgique",
    "CH": "Suisse",
    "LU": "Luxembourg",
    "NL": "Pays-Bas",
    "ES": "Espagne",
    "PT": "Portugal",
    "IT": "Italie",
    "DE": "Allemagne",
    "AT": "Autriche",
    "PL": "Pologne",
    "CZ": "Tchequie",
    "HU": "Hongrie",
    "RO": "Roumanie",
    "GR": "Grece",
    "IE": "Irlande",
    "DK": "Danemark",
    "SE": "Suede",
    "NO": "Norvege",
    "FI": "Finlande",
    "GB": "Royaume-Uni",
    "LT": "Lituanie",
    "LV": "Lettonie",
    "EE": "Estonie",
    "SK": "Slovaquie",
    "SI": "Slovenie",
    "HR": "Croatie",
    "BG": "Bulgarie",
    "TN": "Tunisie",
}

WIKIDATA_COUNTRIES = {
    "France": "Q142",
    "Belgique": "Q31",
    "Suisse": "Q39",
    "Allemagne": "Q183",
    "Pays-Bas": "Q55",
    "Espagne": "Q29",
    "Portugal": "Q45",
    "Italie": "Q38",
    "Autriche": "Q40",
    "Luxembourg": "Q32",
    "Pologne": "Q36",
    "Tchequie": "Q213",
    "Hongrie": "Q28",
    "Roumanie": "Q218",
    "Grece": "Q41",
    "Irlande": "Q27",
    "Danemark": "Q35",
    "Suede": "Q34",
    "Norvege": "Q20",
    "Finlande": "Q33",
    "Royaume-Uni": "Q145",
    "Lituanie": "Q37",
    "Lettonie": "Q211",
    "Estonie": "Q191",
    "Slovaquie": "Q214",
    "Slovenie": "Q215",
    "Croatie": "Q224",
    "Bulgarie": "Q219",
    "Tunisie": "Q948",
}

OSM_COUNTRIES = {
    "France": "FR",
    "Belgique": "BE",
    "Suisse": "CH",
    "Allemagne": "DE",
    "Pays-Bas": "NL",
    "Espagne": "ES",
    "Portugal": "PT",
    "Italie": "IT",
    "Autriche": "AT",
    "Luxembourg": "LU",
    "Pologne": "PL",
    "Tchequie": "CZ",
    "Hongrie": "HU",
    "Roumanie": "RO",
    "Grece": "GR",
    "Irlande": "IE",
    "Danemark": "DK",
    "Suede": "SE",
    "Norvege": "NO",
    "Finlande": "FI",
    "Royaume-Uni": "GB",
    "Lituanie": "LT",
    "Lettonie": "LV",
    "Estonie": "EE",
    "Slovaquie": "SK",
    "Slovenie": "SI",
    "Croatie": "HR",
    "Bulgarie": "BG",
    "Tunisie": "TN",
}


def load_sources() -> list[dict]:
    path = Path(__file__).parent.parent / "config" / "sources.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sources", [])


def _filter_sources(sources: list[dict], pays: str | None) -> list[dict]:
    filtered = []
    for s in sources:
        if not s.get("enabled", True):
            continue
        source_pays = s.get("pays", "").lower()
        if source_pays == "europe":
            filtered.append(s)
        elif pays and source_pays == pays.lower():
            filtered.append(s)
        elif not pays:
            filtered.append(s)
    return filtered


def _collect_ods(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    mapping = source.get("mapping", {})
    params = dict(source.get("params", {}))
    params["limit"] = test_limit or 100

    where_clauses = ["web is not null"]
    if statut:
        type_field = mapping.get("type", "statut_public_prive")
        if "Priv" in statut:
            where_clauses.append(f"{type_field} = 'Prive'")
        else:
            where_clauses.append(f"{type_field} = 'Public'")

    if where_clauses:
        params["where"] = " AND ".join(where_clauses)

    total_count = None
    offset = 0
    total_fetched = 0
    while True:
        params["offset"] = offset
        try:
            resp = requests.get(
                url, params=params, timeout=30, headers={"User-Agent": UA}
            )
            resp.raise_for_status()
            data = resp.json()
            if total_count is None:
                total_count = data.get("total_count", 0)
                print(f"    {source['id']}: total={total_count}")
            records = data.get("results", data.get("records", []))
            if not records:
                break
        except Exception as e:
            print(f"    Erreur ODS {source['id']} (offset={offset}): {e}")
            break

        for item in records:
            raw = {}
            for target_field, source_field in mapping.items():
                val = item.get(source_field)
                if val is None:
                    val = item.get(f"fields.{source_field}")
                raw[target_field] = val
            prospect = normalize_prospect(raw, source["pays"], f"api_{source['id']}")
            results.append(prospect)

        if test_limit:
            break

        total_fetched += len(records)
        if offset % 1000 == 0 and offset > 0:
            print(f"      {source['id']}: offset={offset}, total={total_fetched}")
        offset += 100

        if total_count and offset >= total_count:
            break

    total_fetched = max(total_fetched, len(results))
    print(f"    {source['id']}: {total_fetched} records")
    return results


def _collect_sparql(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    limit = test_limit or source.get("params", {}).get("limit_per_country", 50000)
    rate_limit = source.get("rate_limit_sec", 0.5)

    target_countries = [source.get("pays")]
    if target_countries == ["Europe"]:
        target_country = source.get("_target_country")
        if target_country:
            target_countries = [target_country]
        else:
            target_countries = list(WIKIDATA_COUNTRIES.keys())
        if test_limit:
            target_countries = target_countries[:3]

    for pays_label in target_countries:
        qid = WIKIDATA_COUNTRIES.get(pays_label)
        if not qid:
            continue

        query = f"""SELECT ?school ?schoolLabel ?website WHERE {{
  ?school wdt:P31/wdt:P279* wd:Q3914 .
  ?school wdt:P17 wd:{qid} .
  ?school wdt:P856 ?website .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}
LIMIT {limit}"""

        try:
            r = requests.post(
                url,
                data={"query": query},
                headers={
                    "Accept": "application/sparql-results+json",
                    "User-Agent": UA,
                },
                timeout=120,
            )
            if r.status_code == 503 or r.status_code == 429:
                print(f"    Rate limited Wikidata {pays_label}, waiting 5s...")
                time.sleep(5)
            r.raise_for_status()
            data = r.json()
            bindings = data.get("results", {}).get("bindings", [])

            for b in bindings:
                raw = {}
                for key in ["schoolLabel", "website", "email", "phone"]:
                    val = b.get(key)
                    raw[key] = val.get("value") if val else ""
                raw["countryLabel"] = {"value": pays_label}
                prospect = normalize_prospect(raw, pays_label, f"api_{source['id']}")
                results.append(prospect)

            print(f"    Wikidata {pays_label}: {len(bindings)} records")
            time.sleep(rate_limit)

        except Exception as e:
            print(f"    Erreur Wikidata {pays_label}: {e}")

    return results


def _collect_overpass(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    rate_limit = source.get("rate_limit_sec", 1.0)

    target_countries = [source.get("pays")]
    if target_countries == ["Europe"]:
        target_country = source.get("_target_country")
        if target_country:
            target_countries = [target_country]
        else:
            target_countries = list(OSM_COUNTRIES.keys())
        if test_limit:
            target_countries = target_countries[:3]

    for pays_label in target_countries:
        iso = OSM_COUNTRIES.get(pays_label)
        if not iso:
            continue

        query = f"""[out:json];
area["ISO3166-1"="{iso}"]->.country;
(
  node["amenity"="school"](area.country);
  way["amenity"="school"](area.country);
  relation["amenity"="school"](area.country);
);
out center tags {(test_limit or 10000)};
"""
        try:
            r = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": UA},
                timeout=120,
            )
            if r.status_code == 429:
                print(f"    Rate limited Overpass, waiting 10s...")
                time.sleep(10)
                continue
            r.raise_for_status()
            data = r.json()
            elements = data.get("elements", [])

            for e in elements:
                tags = e.get("tags", {}) or {}
                raw = dict(tags)
                raw["pays_iso"] = iso
                prospect = normalize_prospect(raw, pays_label, f"api_{source['id']}")
                results.append(prospect)

            print(f"    Overpass {pays_label}: {len(elements)} records")
            time.sleep(rate_limit)

        except Exception as e:
            print(f"    Erreur Overpass {pays_label}: {e}")
            continue

    return results


def _collect_ckan(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    params = dict(source.get("params", {}))
    resource_fmt = source.get("resource_format", "csv")

    try:
        r = requests.get(url, params=params, timeout=30, headers={"User-Agent": UA})
        r.raise_for_status()
        data = r.json()

        datasets = []
        if "result" in data and "results" in data["result"]:
            datasets = data["result"]["results"]
        elif "data" in data:
            datasets = data["data"]

        print(f"    CKAN {source['id']}: {len(datasets)} datasets found")

        max_datasets = test_limit // 5 if test_limit else 10
        for ds in datasets[:max_datasets]:
            resources = ds.get("resources", [])
            if not resources and "extras" in ds:
                continue
            for res in resources:
                fmt = (res.get("format") or "").lower()
                if fmt != resource_fmt:
                    continue
                res_url = res.get("url", "")
                if not res_url:
                    continue
                try:
                    rd = requests.get(res_url, timeout=30, headers={"User-Agent": UA})
                    rd.raise_for_status()
                    content = rd.content
                    df = pd.read_csv(io.BytesIO(content), dtype=str).fillna("")
                    max_rows = test_limit if test_limit else len(df)
                    for i, (_, row) in enumerate(df.iterrows()):
                        if i >= max_rows:
                            break
                        raw = row.to_dict()
                        raw["_dataset_title"] = ds.get("title", "")
                        prospect = normalize_prospect(
                            raw, source["pays"], f"api_{source['id']}"
                        )
                        results.append(prospect)
                except Exception as e:
                    print(f"      Erreur ressource {res_url}: {e}")
                    continue

    except Exception as e:
        print(f"    Erreur CKAN {source['id']}: {e}")

    print(f"    CKAN {source['id']}: {len(results)} records")
    return results


def _collect_csv_url(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    mapping = source.get("mapping", {})

    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": UA})
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        if "text/csv" in content_type or url.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(r.content), dtype=str).fillna("")
        else:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(r.text, "html.parser")
            csv_links = [
                a["href"]
                for a in soup.find_all("a", href=True)
                if ".csv" in a["href"].lower()
            ]
            if not csv_links:
                print(f"    Aucun CSV trouve sur {url}")
                return results
            csv_url = csv_links[0]
            if csv_url.startswith("/"):
                from urllib.parse import urlparse

                parsed = urlparse(url)
                csv_url = f"{parsed.scheme}://{parsed.netloc}{csv_url}"
            rc = requests.get(csv_url, timeout=30, headers={"User-Agent": UA})
            rc.raise_for_status()
            df = pd.read_csv(io.BytesIO(rc.content), dtype=str).fillna("")

        max_rows = test_limit if test_limit else len(df)
        for i, (_, row) in enumerate(df.iterrows()):
            if max_rows and i >= max_rows:
                break
            raw = {}
            for target_field, source_field in mapping.items():
                raw[target_field] = row.get(source_field, "")
            if not raw.get("nom"):
                continue
            prospect = normalize_prospect(raw, source["pays"], f"api_{source['id']}")
            results.append(prospect)

    except Exception as e:
        print(f"    Erreur CSV {source['id']}: {e}")

    print(f"    CSV {source['id']}: {len(results)} records")
    return results


def _collect_json_rest(source: dict, statut: str | None = None) -> list[dict]:
    results = []
    test_limit = source.pop("_test_limit", None)
    url = source["url"]
    params = dict(source.get("params", {}))
    mapping = source.get("mapping", {})

    try:
        r = requests.get(url, params=params, timeout=30, headers={"User-Agent": UA})
        r.raise_for_status()
        data = r.json()

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("result", {}).get("items", [])
                or data.get("items", [])
                or data.get("data", [])
            )

        max_items = test_limit if test_limit else 500
        for item in items[:max_items]:
            raw = {}
            for target_field, source_field in mapping.items():
                val = item.get(source_field)
                if isinstance(val, dict):
                    val = val.get("value") or val.get("_value", "")
                raw[target_field] = str(val) if val else ""
            if not raw.get("nom"):
                continue
            prospect = normalize_prospect(raw, source["pays"], f"api_{source['id']}")
            results.append(prospect)

    except Exception as e:
        print(f"    Erreur JSON REST {source['id']}: {e}")

    print(f"    JSON {source['id']}: {len(results)} records")
    return results


HANDLERS = {
    "ods": _collect_ods,
    "sparql": _collect_sparql,
    "overpass": _collect_overpass,
    "ckan": _collect_ckan,
    "csv_url": _collect_csv_url,
    "json_rest": _collect_json_rest,
}


def collect_from_api(statut: str | None = None, pays: str | None = None) -> list[dict]:
    sources = load_sources()
    api_sources = [s for s in sources if s.get("type") == "api"]
    api_sources = _filter_sources(api_sources, pays)

    if not api_sources:
        print(f"  Aucune source API pour {pays}")
        return []

    all_results = []
    for source in api_sources:
        fmt = source.get("format", "ods")
        handler = HANDLERS.get(fmt)
        if not handler:
            print(f"  Format inconnu: {fmt} pour {source['id']}")
            continue

        source_copy = {**source}
        if (
            source_copy.get("pays", "").lower() == "europe"
            and pays
            and pays.lower() != "europe"
        ):
            source_copy["_target_country"] = pays

        print(
            f"\n  [{fmt.upper()}] {source_copy['id']} - {source_copy.get('description', '')}"
        )

        source_timeout = (
            1800 if source_copy.get("format") in ("sparql", "overpass") else 300
        )

        output = []
        exc = []

        def worker():
            try:
                output.append(handler(source_copy, statut))
            except Exception as e:
                exc.append(e)

        t = threading.Thread(target=worker, daemon=True)
        t0 = time.time()
        t.start()
        t.join(source_timeout)

        if t.is_alive():
            print(f"    TIMEOUT {source_copy['id']} ({source_timeout}s depasse)")
            continue
        if exc:
            print(f"    ERREUR {source_copy['id']}: {exc[0]}")
            continue
        if output:
            results = output[0]
            all_results.extend(results)
            print(
                f"    {source_copy['id']}: {len(results)} records en {time.time() - t0:.0f}s"
            )

    return all_results
