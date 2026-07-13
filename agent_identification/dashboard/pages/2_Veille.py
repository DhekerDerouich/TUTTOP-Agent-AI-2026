import streamlit as st
import pandas as pd
from datetime import datetime, date
from dashboard.utils.data_loader import load_veille
from dashboard.utils.runner import run_pipeline

st.title("📅 Veille événementielle EdTech")

tab1, tab2, tab3 = st.tabs(["🚀 Lancer", "📋 Résultats", "📆 Calendrier"])

with tab1:
    st.subheader("Lancer une veille")

    col1, col2 = st.columns(2)
    with col1:
        max_iter = st.number_input("Itérations max", min_value=1, max_value=20, value=5)
    with col2:
        min_score = st.slider("Score minimum", 0, 10, 0)

    resume = st.checkbox("Reprendre depuis le dernier checkpoint")

    if st.button("▶️ Lancer la veille", type="primary", width="stretch"):
        if st.session_state.get("pipeline_running"):
            st.warning("Un pipeline est déjà en cours d'exécution")
        else:
            st.session_state.pipeline_running = True
            placeholder = st.empty()
            with placeholder.container():
                with st.status("Veille en cours...", expanded=True) as status:
                    for line in run_pipeline(
                        "veille",
                        max_iterations=max_iter,
                        min_score=min_score,
                        load_checkpoint=resume,
                    ):
                        st.text(line)
                    status.update(label="Veille terminée", state="complete")
            st.session_state.pipeline_running = False
            st.rerun()

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
                        "source": sheet_name,
                    }
                )

        today = date.today()

        filtres = st.radio(
            "Filtrer par période",
            ["Cette semaine", "Ce mois", "3 mois", "Tous"],
            horizontal=True,
        )

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
            from dateutil.relativedelta import relativedelta

            return today <= d <= today + relativedelta(months=3)

        if filtres == "Cette semaine":
            all_events = [e for e in all_events if e["date"] and _in_week(e["date"])]
        elif filtres == "Ce mois":
            all_events = [e for e in all_events if e["date"] and _in_month(e["date"])]
        elif filtres == "3 mois":
            all_events = [e for e in all_events if e["date"] and _in_3m(e["date"])]

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
                            f"{e['type']} • {e['lieu']} • Score: {e['score']}/10"
                        )

            if without_date:
                with st.expander(
                    f"📌 {len(without_date)} événement(s) sans date précise"
                ):
                    for e in without_date:
                        st.markdown(
                            f"- **{e['nom']}** ({e['type']}) — {e['lieu']} — Score: {e['score']}/10"
                        )
