import re

PRIORITY_COUNTRIES = ["France", "Tunisie", "Belgique", "Suisse"]

PREMIUM_KEYWORDS = [
    r"\binternationale?\b",
    r"\bbilingue\b",
    r"\bbilingual\b",
    r"\bmontessori",
    r"\bsteiner\b",
    r"\bwaldorf\b",
    r"\bdon bosco\b",
    r"\bjesuit[ea]\b",
    r"\brégent\b",
    r"\bregent\b",
    r"\bbritish\b",
    r"\bamerican\b",
    r"\bcambridge\b",
    r"\bib\b",
    r"\bbaccalaureate\b",
    r"\bmilitaire\b",
    r"\bmilitary\b",
    r"\badventist[ea]?\b",
    r"\borthodoxe?\b",
    r"\bcatholique\b",
    r"\bcatholic\b",
    r"\bkatolick[ea]\b",
    r"\bkatolsk[ea]\b",
    r"\bsalesian[oa]\b",
    r"\bévangélique\b",
    r"\bévangelique\b",
    r"\bcooperativa\b",
    r"\bexternato\b",
]

LARGE_KEYWORDS = [
    r"\buniversit[ée]\b",
    r"\buniversity\b",
    r"\buniversität\b",
    r"\buniversidade\b",
    r"\buniverzita\b",
    r"\büniversite\b",
    r"\bfacult[éè]\b",
    r"\bfaculdade\b",
    r"\bfacoltà\b",
    r"\bfaculty\b",
    r"\bcampus\b",
    r"\bacademy\b",
    r"\bacademia\b",
]

MEDIUM_KEYWORDS = [
    r"\bhigh school\b",
    r"\bsecondary\b",
    r"\blyc[ée]e\b",
    r"\bcoll[èe]ge\b",
    r"\bgymnasi[uo]m\b",
    r"\bgymnázium\b",
    r"\bgimnazij[ao]\b",
    r"\bgimnazjum\b",
    r"\bliceul\b",
    r"\bliceo\b",
    r"\bsrednj[ea]\b",
    r"\bstředn[íi]\b",
    r"\binstitut\b",
    r"\bistituto\b",
    r"\binstytut\b",
    r"\bintézmény\b",
    r"\bvoš\b",
    r"\bzuš\b",
    r"\bvidusskola\b",
    r"\bpamatskola\b",
]

SMALL_KEYWORDS = [
    r"\bécole primaire\b",
    r"\bécole élémentaire\b",
    r"\bmaternelle\b",
    r"\bpreschool\b",
    r"\bpre-school\b",
    r"\bkindergarten\b",
    r"\bgarder[ie]\b",
    r"\bcrèche\b",
    r"\bnido\b",
    r"\basilo\b",
    r"\bscuola dell'infanzia\b",
    r"\bförskola\b",
    r"\bbarneskole\b",
    r"\bbarnehage\b",
    r"\bgrundskola\b",
    r"\bpagrindinė\b",
    r"\bprogimnazija\b",
    r"\bdarželis\b",
    r"\bškolka\b",
    r"\bóvoda\b",
]


def _has_pattern(name: str, patterns: list[str]) -> bool:
    if not name:
        return False
    return any(re.search(p, name, re.IGNORECASE) for p in patterns)


def _score_edtech_potential(r: dict) -> int:
    t = r.get("type", "")
    score = 0
    if t == "Privé":
        score += 15
    elif t == "Public":
        score += 5
    source = r.get("source", "")
    if source.startswith("api_"):
        score += 5
    elif source.startswith("web_"):
        score += 3
    return min(score, 20)


def _score_positionnement(nom: str) -> int:
    if _has_pattern(nom, PREMIUM_KEYWORDS):
        return 20
    return 0


def _score_taille(nom: str) -> int:
    if _has_pattern(nom, LARGE_KEYWORDS):
        return 15
    if _has_pattern(nom, MEDIUM_KEYWORDS):
        return 10
    if _has_pattern(nom, SMALL_KEYWORDS):
        return 5
    return 0


def _score_innovation(r: dict) -> int:
    site = r.get("site_web", "") or ""
    email = r.get("email", "") or ""
    score = 0
    if site.startswith("https://"):
        score += 2
    if email:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain.endswith(".edu") or "ac-" in domain or domain.startswith("sch."):
            score += 8
        elif domain and domain not in (
            "gmail.com",
            "yahoo.com",
            "hotmail.com",
            "outlook.com",
            "laposte.net",
        ):
            score += 5
    if site:
        if re.search(r"\b(ent|mon-|e-|web-|digital|online)\b", site, re.IGNORECASE):
            score += 5
    return min(score, 20)


def _score_prospect(r: dict) -> int:
    nom = r.get("nom", "") or ""
    score = 0
    score += _score_edtech_potential(r)
    score += _score_positionnement(nom)
    score += _score_taille(nom)
    score += _score_innovation(r)
    if r.get("site_web"):
        score += 12
    if r.get("email"):
        score += 8
    if r.get("telephone"):
        score += 8
    if r.get("pays") in PRIORITY_COUNTRIES:
        score += 12
    return min(score, 100)


def _qualification_label(score: int) -> str:
    if score >= 50:
        return "Chaud"
    elif score >= 20:
        return "Tiède"
    return "Froid"


def qualify_prospects(records: list[dict]) -> list[dict]:
    print(f"  Qualification de {len(records)} prospects...")
    stats = {"Chaud": 0, "Tiède": 0, "Froid": 0}

    for r in records:
        score = _score_prospect(r)
        r["score"] = score
        r["qualification"] = _qualification_label(score)
        stats[r["qualification"]] += 1

    print(
        f"  Resultat: Chaud={stats['Chaud']}, Tiède={stats['Tiède']}, Froid={stats['Froid']}"
    )
    return records
