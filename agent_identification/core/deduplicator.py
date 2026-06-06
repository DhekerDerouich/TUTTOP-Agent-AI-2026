from models import Prospect


def deduplicate(prospects: list[Prospect]) -> list[Prospect]:
    seen = set()
    result = []
    for p in prospects:
        key = (
            p.site_web.strip().lower() if p.site_web.strip() else p.nom.strip().lower()
        )
        if key and key not in seen:
            seen.add(key)
            result.append(p)
    return result
