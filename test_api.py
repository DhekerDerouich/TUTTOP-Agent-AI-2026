import requests

url = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education/records"
params = {"limit": 3, "where": "statut_public_prive like 'Priv%' and web is not null"}
r = requests.get(url, params=params, timeout=10)
d = r.json()
print("Total:", d.get("total_count"))
for rec in d.get("results", []):
    print(
        rec.get("nom_etablissement"),
        "|",
        rec.get("statut_public_prive"),
        "|",
        rec.get("web"),
    )
