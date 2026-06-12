import re
import time
from langchain_core.messages import HumanMessage
from agent.llm import get_llm

BATCH_SIZE = 200  # Pas de rate-limit avec Ollama local

# ── Keywords Prive ────────────────────────────────────────────────────────────
PRIVATE_KEYWORDS = [
    r"\bpriv[ée]\b",
    r"\bprivada\b",
    r"\bprivata\b",
    r"\bprivate\b",
    r"\bprivatna\b",
    r"\bprywatna\b",
    r"\bsoukrom[ée]\b",
    r"\bmag[áa]n\b",
    r"\bcatholique\b",
    r"\bcatholic\b",
    r"\bkatolick[ea]\b",
    r"\bkatolsk[ea]\b",
    r"\bmontessori",
    r"\bsteiner\b",
    r"\bwaldorf\b",
    r"\binternationale?\b",
    r"\binternacional\b",
    r"\bmilitaire\b",
    r"\bmilitary\b",
    r"\bexternato\b",
    r"\bcooperativa\b",
    r"\bsalesian[oa]\b",
    r"\bdon bosco\b",
    r"\bjesuit[ea]\b",
    r"\brégent\b",
    r"\bregent\b",
    r"\badventist[ea]?\b",
    r"\bévangélique\b",
    r"\bevangélique\b",
    r"\borthodoxe?\b",
]

# ── Keywords Public ───────────────────────────────────────────────────────────
PUBLIC_KEYWORDS = [
    # Générique
    r"\bpublic\b",
    r"\bpublique\b",
    r"\bpública\b",
    r"\bpúblico\b",
    r"\bpubliczna\b",
    r"\bveřejn[áe]\b",
    r"\bstaatliche\b",
    r"\boff?entliche\b",
    r"\bstatale\b",
    # Université / études sup
    r"\buniversit[ée]\b",
    r"\buniversity\b",
    r"\buniversität\b",
    r"\buniversidade\b",
    r"\buniverzita\b",
    r"\büniversite\b",
    r"\bhochschule\b",
    r"\bfachhochschule\b",
    r"\bfacult[éè]\b",
    r"\bfaculdade\b",
    r"\bfacoltà\b",
    r"\bfaculty\b",
    # Institut
    r"\binstytut\b",
    r"\binstitut\b",
    r"\bistituto\b",
    r"\bistituzione\b",
    # École / sup
    r"\bécole sup[ée]rieure\b",
    r"\bescola superior\b",
    r"\bscuola superiore\b",
    r"\bhaute école\b",
    r"\bpolytechnic\b",
    r"\bpolitechnika\b",
    # Academy
    r"\bacademy\b",
    r"\bakademie\b",
    r"\bakademia\b",
    # Collège / lycée
    r"\bcollege\b",
    r"\bcoll[èe]ge\b",
    r"\bcolégio\b",
    r"\bcolegiu\b",
    r"\blyc[ée]e\b",
    r"\blyceum\b",
    r"\bliceum\b",
    r"\bliceu\b",
    # Gymnasium
    r"\bgymnasium\b",
    r"\bgimnazjum\b",
    r"\bgimnázium\b",
    # School (toutes langues — le gros morceau)
    r"\bschools?\b",
    r"\bécole\b",
    r"\becola\b",
    r"\bescola\b",
    r"\bscuola\b",
    r"\bschule\b",
    r"\bškola\b",
    r"\bskola\b",
    r"\bskole\b",
    r"\biskola\b",
    r"\bșcoală\b",
    r"\bszkoła\b",
    r"\bszkola\b",
    r"\bkoulu\b",
    # Primaire / secondaire
    r"\bprimary\b",
    r"\bsecondary\b",
    r"\bhigh school\b",
    r"\bgrammar school\b",
    r"\bpreparatory\b",
    r"\bprep school\b",
    r"\binfants?\b",
    r"\bjuniors?\b",
    r"\bnursery\b",
    r"\belementary\b",
    r"\bkindergarten\b",
    r"\bgrundschule\b",
    r"\bmittelschule\b",
    r"\brealschule\b",
    r"\bosnovn[aa]\b",
    r"\bvideregående\b",
    # Français
    r"\bmaternelle\b",
    r"\bprimaire\b",
    r"\bere(a|ea)\b",
    r"\bcfppa\b",
    r"\blegta\b",
    r"\blp[ \b]",
    r"\blycée pro\b",
    # Italien
    r"\bmedie\b",
    r"\belementare\b",
    # Roumain
    r"\bfacultate\b",
    r"\bșcoala\b",
    r"\bscoala\b",
    r"\bgimnazială\b",
    r"\bgimnaziala\b",
    r"\bliceul\b",
    r"\bcolegiul\b",
    r"\btehnologic\b",
    r"\btehnic\b",
    r"\bteoretic\b",
    r"\bnațional\b",
    r"\bprimară\b",
    r"\bgrădinița\b",
    r"\bgradinita\b",
    r"\bcentrul\b",
    r"\bgenerală\b",
    r"\bgimnaziul\b",
    r"\bcopiilor\b",
    # Italien
    r"\bliceo\b",
    r"\bscientifico\b",
    r"\bclassico\b",
    r"\baccademia\b",
    r"\bprofessionale\b",
    r"\basilo\b",
    r"\bnido\b",
    r"\bartistico\b",
    r"\biis\b",
    r"\bconservatorio\b",
    r"\btecnico\b",
    r"\bistruzione\b",
    r"\bsuperiore\b",
    # Lituanien
    r"\bmokykla\b",
    r"\bpagrindinė\b",
    r"\bprogimnazija\b",
    r"\bvidurinė\b",
    r"\bpradinė\b",
    r"\bdarželis\b",
    r"\bmokymo\b",
    # Suédois / Norvégien / Danois
    r"\bförskola\b",
    r"\bforskola\b",
    r"\bgymnasieskola\b",
    r"\bgymnasiet\b",
    r"\bgrundskola\b",
    r"\bbarneskole\b",
    r"\bunGDomsskole\b",
    r"\bunGDomsskule\b",
    r"\bskule\b",
    r"\befterskole\b",
    r"\bfolkhögskola\b",
    r"\bfolkhogskola\b",
    r"\bhögskola\b",
    r"\bhogskola\b",
    r"\bhøgskole\b",
    r"\bhøyskole\b",
    r"\buniversitet\b",
    r"\bgrunnskole\b",
    r"\bvidaregåande\b",
    r"\bfriskola\b",
    r"\bkunskaps\b",
    r"\bkomvux\b",
    r"\bnti\b",
    r"\bidrætsefterskole\b",
    r"\bidraetsefterskole\b",
    # Composés nordiques (sans \b final pour attraper les mots composés et formes definies)
    r"\bskola",
    r"\bskole",
    r"\bunGDomsskole",
    r"\bförskola",
    r"\bgymnasieskola",
    r"\bgrundskola",
    r"\bbarneskole",
    r"\bfolkhögskola",
    r"\bhögskola",
    r"\bhøgskole",
    r"\bhøyskole",
    r"\bgrunnskole",
    r"\bfriskola",
    r"\befterskola",
    r"\bfriskole",
    r"\bfolkehøgskole",
    r"\bbarneskule",
    # Slovaque / Tchèque
    r"\bgymnázium\b",
    r"\bgymnazium\b",
    r"\bškolka\b",
    r"\bskolka\b",
    r"\bzuš\b",
    r"\bvoš\b",
    # Slovène / Croate
    r"\bšola\b",
    r"\bšolski\b",
    r"\bsrednja\b",
    r"\bosnovna\b",
    r"\bgimnazija\b",
    r"\bpodružnica\b",
    # Gallois
    r"\bysgol\b",
    # Polonais
    r"\btechnikum\b",
    r"\bszkół\b",
    r"\bszkoly\b",
    r"\bzespół\b",
    r"\buniwersytet\b",
    # Hongrois
    r"\bállami\b",
    r"\begyetem\b",
    r"\bszakközépiskola\b",
    r"\bszakkepzo\b",
    r"\báltalános\b",
    r"\bkollégium\b",
    r"\bkollegium\b",
    r"\bszakiskola\b",
    r"\bszakgimnázium\b",
    r"\bközépiskola\b",
    r"\bintézmény\b",
    r"\bisko\b",
    r"\btagiskola\b",
    r"\bzeneiskola\b",
    # Portugais
    r"\bjardim\b",
    r"\binfância\b",
    r"\beducação\b",
    r"\bformação\b",
    r"\bprofissional\b",
    r"\bjardim de infância\b",
    r"\beb1\b",
    r"\beb2\b",
    r"\beb3\b",
    r"\bjic\b",
    r"\bjip\b",
    # Espagnol / Portugais / Italien
    r"\bcentro\b",
    r"\bescolar\b",
    r"\bacademia\b",
    r"\binstituto\b",
    r"\beducativo\b",
    r"\bassociação\b",
    # Italien
    r"\bscuole\b",
    r"\bcollegio\b",
    r"\belementari\b",
    r"\bscolastico\b",
    r"\bcircolo\b",
    r"\bdidattico\b",
    r"\bprofessionale\b",
    # Lituanien (formes génitives)
    r"\bmokyklos\b",
    r"\bugdymo\b",
    r"\bcentras\b",
    # Irlandais
    r"\bcoláiste\b",
    r"\bscoil\b",
    # Norvégien (kindergarten, folk school)
    r"\bbarnehage\b",
    r"\bfolkehøgskole\b",
    # Général (toutes langues)
    r"\bconservatoire\b",
    r"\bconservatory\b",
    r"\bconservatorio\b",
    r"\bconservatório\b",
    r"\bacadémie\b",
    r"\boppvekstsenter\b",
    r"\bcollegium\b",
    r"\bcampus\b",
    r"\btag\b",
    r"\binternat\b",
    r"\bpreschool\b",
    r"\bchildren'?s?\b",
    r"\binstitute\b",
    r"\binstitute of\b",
    r"\binternational\b",
    # Allemand
    r"\bberufsschule\b",
    r"\bvolksschule\b",
    r"\bhauptschule\b",
    r"\bgesamtschule\b",
    r"\brealschule\b",
    # Luxembourgeois
    r"\blycée classique\b",
    r"\bgrondschoul\b",
    # Letton
    r"\bvidusskola\b",
    r"\bpamatskola\b",
    r"\bsākumskola\b",
    # Finnois
    r"\bkoulu\b",
    r"\blukio\b",
    r"\bperuskoulu\b",
    # Grec
    r"\bγυμνάσιο\b",
    r"\bσχολείο\b",
    # Autres
    r"\bsixth form\b",
    r"\bfurther education\b",
    r"\bfe college\b",
]

_PRIVATE_RE = [re.compile(p, re.IGNORECASE) for p in PRIVATE_KEYWORDS]
_PUBLIC_RE = [re.compile(p, re.IGNORECASE) for p in PUBLIC_KEYWORDS]


def _keyword_classify(r: dict) -> str:
    nom = (r.get("nom") or "").strip()
    if not nom:
        return "Inconnu"
    for pat in _PRIVATE_RE:
        if pat.search(nom):
            return "Privé"
    for pat in _PUBLIC_RE:
        if pat.search(nom):
            return "Public"
    return "Inconnu"


def _keyword_pass(records: list[dict]) -> tuple[list[dict], list[dict]]:
    classified, unknown = [], []
    for r in records:
        t = _keyword_classify(r)
        if t != "Inconnu":
            r["type"] = t
            classified.append(r)
        else:
            unknown.append(r)
    total = len(classified) + len(unknown)
    p = len(classified) / total * 100 if total else 0
    print(
        f"    Keywords: {len(classified)} classes ({p:.0f}%) | {len(unknown)} restants"
    )
    return classified, unknown


# ── LLM : appel local (Ollama) ou distant (Groq, OpenAI, Gemini) ─────────────

CLASSIFY_PROMPT = """Tu es un expert en etablissements scolaires europeens.
Classifie chaque etablissement: "Prive", "Public" ou "Inconnu".

Regles:
- Prive: ecole privee, catholique, internationale, Montessori, Steiner, sous contrat
- Public: ecole publique, college, lycee, universite, academy, school, skola, schule
- Inconnu: si impossible a determiner

REPONDS UNIQUEMENT avec ce format (une ligne par numero):
1: Prive
2: Public
3: Inconnu

Etablissements:"""


def _parse_llm(text: str, batch: list[dict]) -> list[dict]:
    results = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        try:
            idx_str, val = line.split(":", 1)
            idx = int(re.sub(r"[^\d]", "", idx_str))
            v = val.strip().strip("'\"").lower()
            if any(x in v for x in ("priv", "private")):
                results[idx] = "Privé"
            elif any(x in v for x in ("public", "publique")):
                results[idx] = "Public"
            else:
                results[idx] = "Inconnu"
        except (ValueError, IndexError):
            continue
    for i, r in enumerate(batch, 1):
        if i in results:
            r["type"] = results[i]
    return batch


def _llm_batch(batch: list[dict], llm) -> list[dict]:
    if not batch:
        return batch
    lines = [
        f'{i}. "{r.get("nom", "")}" ({r.get("pays", "")})'
        for i, r in enumerate(batch, 1)
    ]
    prompt = CLASSIFY_PROMPT + "\n" + "\n".join(lines)
    try:
        msg = llm.invoke([HumanMessage(content=prompt)])
        return _parse_llm(msg.content, batch)
    except Exception as e:
        print(f"      Erreur LLM: {e}")
        return batch


def _llm_loop(records: list[dict], provider: str, batch_size: int = 200) -> list[dict]:
    if not records:
        return records
    llm = get_llm(provider=provider)
    batches = [records[i : i + batch_size] for i in range(0, len(records), batch_size)]
    total = len(batches)
    results, t0 = [], time.time()
    print(
        f"\n    [{provider.upper()}] {len(records)} prospects -> {total} lots de {batch_size}"
    )
    for i, batch in enumerate(batches, 1):
        done = _llm_batch(batch, llm)
        results.extend(done)
        ok = sum(1 for x in done if x.get("type") != "Inconnu")
        el = time.time() - t0
        print(f"    Lot {i:>3}/{total} | {ok}/{len(batch)} classes | {el:.0f}s ecoules")
    return results


# ── Point d'entree principal ──────────────────────────────────────────────────


def classify_types(
    records: list[dict], provider: str = "ollama", batch_size: int = 200
) -> list[dict]:
    t0 = time.time()
    unknown = [r for r in records if r.get("type") in ("Inconnu", "", None)]
    known = [r for r in records if r.get("type") not in ("Inconnu", "", None)]
    if not unknown:
        print("  [CLASSIFY] Aucun Inconnu -> skip")
        return records
    print(f"\n  [CLASSIFY] {len(unknown)} Inconnus sur {len(records)} total")

    kw_classified, remaining = _keyword_pass(unknown)
    if not remaining:
        el = time.time() - t0
        print(f"  [CLASSIFY] Termine en {el:.1f}s (keywords only)")
        return known + kw_classified

    print(f"\n  [CLASSIFY] {len(remaining)} ambigus -> LLM ({provider})")
    llm_classified = _llm_loop(remaining, provider=provider, batch_size=batch_size)
    all_records = known + kw_classified + llm_classified

    el = time.time() - t0
    p = sum(1 for r in all_records if r.get("type") == "Privé")
    u = sum(1 for r in all_records if r.get("type") == "Public")
    i = sum(1 for r in all_records if r.get("type") == "Inconnu")
    print(f"\n  [CLASSIFY] Termine en {el:.1f}s | Prive={p}, Public={u}, Inconnu={i}")
    return all_records
