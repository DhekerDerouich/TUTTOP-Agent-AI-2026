import os
import json
import time
from pathlib import Path
from datetime import date
from typing import Optional
import requests

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "rocketreach_cache.json"
USAGE_FILE = Path(__file__).resolve().parent.parent / "data" / "rocketreach_usage.json"
DAILY_LIMIT = 40

API_BASE = "https://api.rocketreach.co/v2/api"


class RocketReachClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ROCKETREACH_API_KEY", "")
        self._cache = self._load_cache()
        self._usage = self._load_usage()

    # ---- Cache ----

    def _load_cache(self) -> dict:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _cache_key(self, **params) -> str:
        return json.dumps({k: v for k, v in sorted(params.items()) if v})

    def _get_from_cache(self, **params) -> Optional[dict]:
        key = self._cache_key(**params)
        entry = self._cache.get(key)
        if entry:
            return entry.get("result")
        return None

    def _set_cache(self, result: dict, **params):
        key = self._cache_key(**params)
        self._cache[key] = {
            "params": {k: v for k, v in sorted(params.items()) if v},
            "result": result,
            "cached_at": time.time(),
        }
        self._save_cache()

    # ---- Usage tracking ----

    def _load_usage(self) -> dict:
        if USAGE_FILE.exists():
            try:
                data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
                if data.get("date") == str(date.today()):
                    return data
            except Exception:
                pass
        return {"date": str(date.today()), "count": 0}

    def _save_usage(self):
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(
            json.dumps(self._usage, ensure_ascii=False), encoding="utf-8"
        )

    @property
    def remaining(self) -> int:
        usage = self._load_usage()
        return max(0, DAILY_LIMIT - usage.get("count", 0))

    @property
    def used_today(self) -> int:
        usage = self._load_usage()
        return usage.get("count", 0)

    def _increment_usage(self):
        usage = self._load_usage()
        usage["count"] = usage.get("count", 0) + 1
        self._usage = usage
        self._save_usage()

    # ---- API calls ----

    def _call_api(self, payload: dict) -> Optional[dict]:
        if not self.api_key:
            return {"error": "ROCKETREACH_API_KEY non configurée"}

        if self.remaining <= 0:
            return {"error": "Quota quotidien épuisé (40/40). Réessaie demain."}

        try:
            resp = requests.post(
                f"{API_BASE}/person/lookup",
                headers={
                    "Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException as e:
            return {"error": f"Erreur réseau: {e}"}

        if resp.status_code == 429:
            return {
                "error": "Quota API dépassé (rate limit). Réessaie dans quelques minutes."
            }
        if resp.status_code == 401:
            return {"error": "Clé API invalide. Vérifie ROCKETREACH_API_KEY."}
        if resp.status_code == 404:
            return {"error": "Aucun profil trouvé pour ces critères."}

        if resp.status_code != 200:
            return {"error": f"Erreur API {resp.status_code}: {resp.text[:300]}"}

        self._increment_usage()
        return resp.json()

    # ---- Public methods ----

    def lookup_by_linkedin(self, linkedin_url: str) -> dict:
        cached = self._get_from_cache(linkedin_url=linkedin_url)
        if cached:
            return {**cached, "_cached": True}

        result = self._call_api({"linkedin_url": linkedin_url})
        if result and "error" not in result:
            self._set_cache(result, linkedin_url=linkedin_url)
        return result

    def lookup_by_name_company(
        self,
        name: str,
        company: str = "",
        location: str = "",
        title: str = "",
    ) -> dict:
        cached = self._get_from_cache(
            name=name, company=company, location=location, title=title
        )
        if cached:
            return {**cached, "_cached": True}

        payload = {"name": name}
        if company:
            payload["company"] = company
        if location:
            payload["location"] = location
        if title:
            payload["title"] = title

        result = self._call_api(payload)
        if result and "error" not in result:
            self._set_cache(
                result, name=name, company=company, location=location, title=title
            )
        return result

    # ---- Cache management ----

    def list_cache(self) -> list[dict]:
        return [
            {"params": v["params"], "cached_at": v["cached_at"]}
            for v in self._cache.values()
        ]

    def clear_cache(self):
        self._cache = {}
        self._save_cache()

    def get_all_cached_results(self) -> list[dict]:
        results = []
        for key, entry in self._cache.items():
            person = entry.get("result", {}).get("person", {})
            if person:
                results.append(
                    {
                        "name": person.get("name", ""),
                        "linkedin_url": person.get("linkedin_url", ""),
                        "title": person.get("current_title", ""),
                        "company": (person.get("current_company") or {}).get(
                            "name", ""
                        ),
                        "emails": ", ".join(
                            e.get("email", "") for e in (person.get("emails") or [])
                        ),
                        "search_params": entry.get("params", {}),
                        "cached_at": entry.get("cached_at", 0),
                    }
                )
        return results


def extract_person_info(api_result: dict) -> dict:
    """Extract useful fields from the API response."""
    if not api_result or "error" in api_result:
        return {"error": api_result.get("error", "Réponse vide")}

    person = api_result.get("person", api_result)
    if not person:
        return {"error": "Aucune personne dans la réponse"}

    emails_raw = person.get("emails") or []
    phones_raw = person.get("phones") or []
    current_company = person.get("current_company") or {}
    work_history = person.get("work_history") or []

    info = {
        "id": person.get("id"),
        "name": person.get("name", ""),
        "title": person.get("current_title", ""),
        "company": current_company.get("name", ""),
        "location": person.get("location", ""),
        "linkedin_url": person.get("linkedin_url", ""),
        "emails": [
            {
                "email": e.get("email", ""),
                "validation": e.get("smtp_validation", "unknown"),
                "type": e.get("type", ""),
            }
            for e in emails_raw
        ],
        "phones": [
            {"phone": p.get("phone", ""), "type": p.get("type", "")} for p in phones_raw
        ],
        "work_history": [
            {
                "company": w.get("company", ""),
                "title": w.get("title", ""),
                "start": w.get("start_date", ""),
                "end": w.get("end_date", ""),
            }
            for w in work_history[:5]
        ],
        "education": person.get("education", []),
        "profile_url": person.get("rr_profile_url", ""),
        "skills": person.get("skills", []),
        "industry": person.get("industry", ""),
        "_cached": api_result.get("_cached", False),
    }
    return info
