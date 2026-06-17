"""Verifie les sites en 3 lots + sauvegarde intermediaire."""

import warnings, time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests as req
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

DATA = Path(__file__).parent.parent / "data"
CSV = DATA / "urls_a_verifier.csv"
XLSX = DATA / "prospect_chauds.xlsx"
CACHE = DATA / "cache_sites.json"

# Charger deja verifies
deja_fait = {}
if CACHE.exists():
    with open(CACHE, encoding="utf-8") as f:
        deja_fait = json.load(f)
    print(f"Deja verifies: {len(deja_fait)}")

urls_df = pd.read_csv(CSV, dtype=str)
urls = [u for u in urls_df["site_web"].tolist() if u not in deja_fait]
print(f"Restants a verifier: {len(urls)}")

if not urls:
    print("Tout deja verifie!")
else:

    def check(url):
        try:
            r = req.get(
                url,
                timeout=3,
                verify=False,
                stream=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            ok = r.status_code < 400 or r.status_code == 403
            r.close()
            return (url, ok)
        except:
            return (url, False)

    done = 0
    lot = 0
    t0 = time.time()

    while done < len(urls):
        batch = urls[done : done + 4000]
        if not batch:
            break

        valides = {}
        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = {pool.submit(check, u): u for u in batch}
            for f in as_completed(futures):
                u, ok = f.result()
                valides[u] = ok
                done += 1

        # Sauvegarder le lot
        deja_fait.update({u: ("Oui" if ok else "Non") for u, ok in valides.items()})
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(deja_fait, f)

        lot += 1
        elapsed = time.time() - t0
        ok_count = sum(1 for v in valides.values() if v)
        print(
            f"  Lot {lot}: +{len(batch)} verifiees | OK: {ok_count} | Total: {done}/{len(urls)} | {elapsed:.0f}s"
        )

    t = time.time() - t0
    print(f"\nTermine en {t:.0f}s")

print("\nMise a jour du XLSX...")
df = pd.read_excel(XLSX, dtype=str).fillna("")
df["site_valide"] = df["site_web"].map(deja_fait).fillna("")
df.to_excel(XLSX, index=False, engine="openpyxl")
ok_final = (df["site_valide"] == "Oui").sum()
print(f"Fait. Sites OK: {ok_final}/{len(df)} | -> {XLSX}")
