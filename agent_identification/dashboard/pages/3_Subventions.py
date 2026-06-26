import streamlit as st
import pandas as pd
from dashboard.utils.data_loader import load_subventions
from dashboard.utils.runner import run_pipeline

st.title("💰 Aides & Subventions EdTech")

tab1, tab2 = st.tabs(["🚀 Lancer", "📋 Résultats"])

with tab1:
    st.subheader("Lancer la recherche de subventions")

    col1, col2 = st.columns(2)
    with col1:
        max_iter = st.number_input("Itérations max", min_value=1, max_value=20, value=5)
    with col2:
        min_score = st.slider("Score minimum", 0, 10, 0)

    if st.button("▶️ Lancer la recherche", type="primary", width="stretch"):
        if st.session_state.get("pipeline_running"):
            st.warning("Un pipeline est déjà en cours d'exécution")
        else:
            st.session_state.pipeline_running = True
            placeholder = st.empty()
            with placeholder.container():
                with st.status("Recherche en cours...", expanded=True) as status:
                    for line in run_pipeline(
                        "subventions",
                        subventions_max_iterations=max_iter,
                        min_score=min_score,
                    ):
                        st.text(line)
                    status.update(label="Recherche terminée", state="complete")
            st.session_state.pipeline_running = False
            st.rerun()

with tab2:
    st.subheader("Subventions trouvées")
    df = load_subventions()

    if df.empty:
        st.info("Aucune donnée de subventions trouvée")
    else:
        st.success(f"{len(df)} subventions trouvées")

        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            if "Region" in df.columns:
                regions = ["Toutes"] + sorted(df["Region"].dropna().unique().tolist())
                selected_region = st.selectbox("Filtrer par région", regions)
        with col_f2:
            if "Statut" in df.columns:
                statuts = ["Tous"] + sorted(df["Statut"].dropna().unique().tolist())
                selected_statut = st.selectbox("Filtrer par statut", statuts)
        with col_f3:
            if "Priorite" in df.columns:
                priorites = ["Toutes"] + sorted(
                    df["Priorite"].dropna().unique().tolist()
                )
                selected_priorite = st.selectbox("Filtrer par priorité", priorites)
        with col_f4:
            if "Type aide" in df.columns:
                types = ["Tous"] + sorted(df["Type aide"].dropna().unique().tolist())
                selected_type = st.selectbox("Filtrer par type d'aide", types)

        filtered = df.copy()
        if "Region" in df.columns and selected_region != "Toutes":
            filtered = filtered[filtered["Region"] == selected_region]
        if "Statut" in df.columns and selected_statut != "Tous":
            filtered = filtered[filtered["Statut"] == selected_statut]
        if "Priorite" in df.columns and selected_priorite != "Toutes":
            filtered = filtered[filtered["Priorite"] == selected_priorite]
        if "Type aide" in df.columns and selected_type != "Tous":
            filtered = filtered[filtered["Type aide"] == selected_type]

        st.caption(f"{len(filtered)} subventions après filtrage")

        cols = st.multiselect(
            "Colonnes à afficher",
            list(filtered.columns),
            default=[
                "Nom",
                "Organisme",
                "Region",
                "Deadline",
                "Score",
                "Priorite",
                "Statut",
                "Type aide",
            ],
        )
        if cols:
            st.dataframe(filtered[cols], width="stretch", hide_index=True)

        st.download_button(
            "📥 Télécharger (CSV)",
            filtered.to_csv(index=False).encode("utf-8-sig"),
            "subventions_filtered.csv",
        )
