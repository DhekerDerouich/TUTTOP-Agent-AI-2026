import streamlit as st
import pandas as pd
from dashboard.utils.data_loader import load_veille
from dashboard.utils.runner import run_pipeline

st.title("📅 Veille événementielle EdTech")

tab1, tab2 = st.tabs(["🚀 Lancer", "📋 Résultats"])

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
