import streamlit as st
import pandas as pd
import io
import contextlib
from datetime import datetime, date
from pathlib import Path
from dashboard.utils.data_loader import load_veille


def _run_veille_pipeline(max_iterations=5, min_score=0):
    """Run veille pipeline in-process. Yields log lines."""
    import os as _os

    # Diagnostic des cles API
    for _k in [
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "LANGCHAIN_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
    ]:
        _v = _os.environ.get(_k, "") or ""
        yield f"[ENV] {_k}={'OK (' + _v[:8] + '...)' if _v else 'MANQUANT'}"

    from agent.veille_graph import agent as veille_agent
    from agent.veille_nodes import VeilleState

    initial_state: VeilleState = {
        "messages": [],
        "hackathons": [],
        "evenements": [],
        "queries_executees": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "store": {"raw_data": []},
    }

    yield f"Lancement de la veille ({max_iterations} iterations max)"

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        config = {"configurable": {"thread_id": "veille-streamlit"}}
        try:
            for event in veille_agent.stream(initial_state, config):
                pass
        except Exception as e:
            yield f"ERREUR: {e}"
            return

        try:
            final = veille_agent.get_state(config)
            values = final.values
        except Exception as e:
            yield f"ERREUR get_state: {e}"
            return

    for line in buf.getvalue().splitlines():
        stripped = line.strip()
        if stripped:
            yield stripped

    hackathons = values.get("hackathons", [])
    evenements = values.get("evenements", [])

    if min_score > 0:
        hackathons = [
            h for h in hackathons if getattr(h, "score_strategique", 0) >= min_score
        ]
        evenements = [
            e for e in evenements if getattr(e, "score_strategique", 0) >= min_score
        ]

    yield f"Resultats: {len(hackathons)} hackathons, {len(evenements)} evenements"

    DATA = Path(__file__).resolve().parent.parent.parent / "data"

    if not hackathons and not evenements:
        yield "AUCUN RESULTAT — Les fichiers existants sont conserves intacts"
        return

    hack_data = [
        h.model_dump() if hasattr(h, "model_dump") else dict(h) for h in hackathons
    ]
    event_data = [
        e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in evenements
    ]

    pd.DataFrame(hack_data).to_csv(
        DATA / "veille_hackathons.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(event_data).to_csv(
        DATA / "veille_evenements.csv", index=False, encoding="utf-8-sig"
    )

    with pd.ExcelWriter(DATA / "veille.xlsx", engine="openpyxl") as w:
        pd.DataFrame(hack_data).to_excel(w, sheet_name="Hackathons", index=False)
        pd.DataFrame(event_data).to_excel(w, sheet_name="Evenements", index=False)

    yield f"Fichiers mis a jour: {len(hackathons)} hackathons + {len(evenements)} evenements -> veille.xlsx"


st.title("📅 Veille événementielle EdTech")

tab1, tab2, tab3 = st.tabs(["🚀 Lancer", "📋 Résultats", "📆 Calendrier"])

with tab1:
    st.subheader("Lancer une veille")

    col1, col2 = st.columns(2)
    with col1:
        max_iter = st.number_input("Itérations max", min_value=1, max_value=20, value=5)
    with col2:
        min_score = st.slider("Score minimum", 0, 10, 0)

    if st.button("▶️ Lancer la veille", type="primary", use_container_width=True):
        if st.session_state.get("pipeline_running"):
            st.warning("Un pipeline est déjà en cours d'exécution")
        else:
            st.session_state.pipeline_running = True
            had_results = False
            placeholder = st.empty()
            with placeholder.container():
                with st.status("Veille en cours...", expanded=True) as status:
                    for line in _run_veille_pipeline(
                        max_iterations=max_iter,
                        min_score=min_score,
                    ):
                        st.text(line)
                        if "Fichiers mis a jour" in line:
                            had_results = True
                    status.update(label="Veille terminée", state="complete")
            st.session_state.pipeline_running = False
            if had_results:
                st.rerun()
            else:
                st.warning(
                    "Aucun nouveau résultat trouvé. Les données existantes sont conservées."
                )

with tab2:
    st.subheader("Résultats de la veille")
    veille_data = load_veille()

    if not veille_data:
        st.info("Aucune donnée de veille trouvée")
    else:
        for sheet_name, df in veille_data.items():
            with st.expander(f"{sheet_name} ({len(df)} entrées)", expanded=True):
                if df.empty:
                    st.info(f"Aucun {sheet_name.lower()}")
                    continue

                cols = st.multiselect(
                    f"Colonnes à afficher — {sheet_name}",
                    list(df.columns),
                    default=[
                        c
                        for c in [
                            "nom",
                            "type",
                            "date",
                            "lieu",
                            "score_strategique",
                            "raison",
                        ]
                        if c in df.columns
                    ],
                    key=f"cols_{sheet_name}",
                )
                if cols:
                    st.dataframe(df[cols], width="stretch", hide_index=True)

                if "score_strategique" in df.columns:
                    st.bar_chart(df["score_strategique"].value_counts().sort_index())

                csv = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    f"📥 Télécharger {sheet_name} (CSV)",
                    csv,
                    f"veille_{sheet_name.lower()}.csv",
                    key=f"dl_{sheet_name}",
                )

with tab3:
    st.subheader("Événements à venir dans la région Azur")
    st.caption("Les liens sont dans les détails de chaque événement ▼")
    veille_data = load_veille()

    if not veille_data:
        st.info("Aucune donnée de veille trouvée")
    else:
        all_events = []
        for sheet_name, df in veille_data.items():
            if df.empty:
                continue
            for _, row in df.iterrows():
                date_raw = row.get("date") or row.get("date_debut") or ""
                lieu = row.get("lieu", "")
                nom = row.get("nom", "")
                type_e = row.get("type", sheet_name.rstrip("s"))
                score = row.get("score_strategique", 0)
                url = row.get("url", "")
                raison = row.get("raison", "")
                pertinence = row.get("pertinence_tuttop", "")
                description = row.get("description", "")
                thematiques = row.get("thematiques", "")
                source = row.get("source", "")
                source_engine = row.get("source_engine", "")

                parsed = None
                if isinstance(date_raw, str) and "/" in date_raw:
                    parts = date_raw.strip().split("/")
                    if len(parts) == 3:
                        try:
                            parsed = datetime(
                                int(parts[2]), int(parts[1]), int(parts[0])
                            ).date()
                        except ValueError:
                            pass

                all_events.append(
                    {
                        "nom": nom,
                        "type": type_e,
                        "date": parsed,
                        "date_raw": date_raw,
                        "lieu": lieu,
                        "score": score,
                        "url": url,
                        "raison": raison,
                        "pertinence": pertinence,
                        "description": description,
                        "thematiques": thematiques,
                        "source": source,
                        "source_engine": source_engine,
                        "sheet": sheet_name,
                    }
                )

        today = date.today()

        col_filtre, col_tri = st.columns([2, 1])
        with col_filtre:
            filtres = st.radio(
                "Période",
                ["Cette semaine", "Ce mois", "3 mois", "Tous"],
                horizontal=True,
            )
        with col_tri:
            score_min = st.slider("Score min", 0, 10, 5)

        def _in_week(d):
            if d is None:
                return False
            w = d.isocalendar()[1]
            return w == today.isocalendar()[1] and d.year == today.year

        def _in_month(d):
            if d is None:
                return False
            return d.month == today.month and d.year == today.year

        def _in_3m(d):
            if d is None:
                return False
            return today <= d and (d - today).days <= 90

        if filtres == "Cette semaine":
            all_events = [e for e in all_events if e["date"] and _in_week(e["date"])]
        elif filtres == "Ce mois":
            all_events = [e for e in all_events if e["date"] and _in_month(e["date"])]
        elif filtres == "3 mois":
            all_events = [e for e in all_events if e["date"] and _in_3m(e["date"])]

        all_events = [e for e in all_events if e["score"] >= score_min]

        with_date = [e for e in all_events if e["date"] is not None]
        without_date = [e for e in all_events if e["date"] is None]
        with_date.sort(key=lambda x: x["date"])

        if not with_date and not without_date:
            st.info(f"Aucun événement {filtres.lower()}")
        else:
            st.caption(
                f"{len(with_date)} événement(s) avec date • "
                f"{len(without_date)} sans date précise"
            )

            for e in with_date:
                delta = (e["date"] - today).days
                if delta < 0:
                    badge = "🔴 Passé"
                elif delta == 0:
                    badge = "🟡 Aujourd'hui"
                elif delta <= 7:
                    badge = "🟢 Cette semaine"
                elif delta <= 30:
                    badge = "🔵 Ce mois"
                else:
                    badge = "⏳ À venir"

                with st.container(border=True):
                    cols = st.columns([1, 4])
                    with cols[0]:
                        st.markdown(f"### {e['date'].strftime('%d/%m')}")
                        st.caption(e["date"].strftime("%a").capitalize())
                    with cols[1]:
                        st.markdown(f"**{e['nom']}**  {badge}")
                        st.caption(
                            f"{e['type']} • {e['lieu']} • Score: **{e['score']}/10**"
                        )

                    with st.expander("Détails"):
                        is_llm = "connaissance" in str(e["source"]).lower()
                        url_str = str(e["url"]) if pd.notna(e["url"]) else ""
                        if url_str.startswith("http") and not is_llm:
                            if "instagram" in url_str:
                                st.markdown(
                                    f"📸 **Publication Instagram :** [Voir le post]({url_str})"
                                )
                            elif any(
                                k in url_str
                                for k in [
                                    "tribuca",
                                    "radiofrance",
                                    "lactudelorientation",
                                ]
                            ):
                                st.markdown(
                                    f"📰 **Article :** [Lire l'article]({url_str})"
                                )
                            else:
                                st.markdown(
                                    f"🔗 **Lien :** [Accéder à l'événement]({url_str})"
                                )
                        elif is_llm:
                            st.markdown(
                                "ℹ️ *Information générée par IA — aucun lien disponible*"
                            )
                        if e["description"] and str(e["description"]) not in (
                            "nan",
                            "",
                        ):
                            st.markdown(f"**Description :** {e['description']}")
                        if e["raison"] and str(e["raison"]) not in ("nan", ""):
                            st.markdown(f"**Raison :** {e['raison']}")
                        if e["pertinence"] and str(e["pertinence"]) not in ("nan", ""):
                            st.markdown(f"**Pertinence TUT'TOP :** {e['pertinence']}")
                        if e["thematiques"] and str(e["thematiques"]) not in (
                            "nan",
                            "",
                        ):
                            st.markdown(f"**Thématiques :** {e['thematiques']}")
                        st.caption(
                            f"Source : {e['source']} • Moteur : {e['source_engine']}"
                        )

            if without_date:
                with st.expander(
                    f"📌 {len(without_date)} événement(s) sans date précise"
                ):
                    for e in without_date:
                        st.markdown(
                            f"- **{e['nom']}** ({e['type']}) — {e['lieu']} — Score: {e['score']}/10"
                        )
                        if e["raison"] and str(e["raison"]) not in ("nan", ""):
                            st.markdown(f"  > {e['raison']}")
