import streamlit as st
import pandas as pd
from dashboard.utils.data_loader import (
    load_subventions,
    load_veille,
    load_prospects,
)

st.title("📊 Tableau de bord TUT'TOP")

col1, col2, col3, col4 = st.columns(4)

subv = load_subventions()
veille = load_veille()
prospects_all = load_prospects("all")
prospects_chauds = load_prospects("chauds")

with col1:
    st.metric("🏫 Tous les prospects", len(prospects_all))

with col2:
    total_events = sum(len(df) for df in veille.values()) if veille else 0
    st.metric("📅 Événements / Hackathons", total_events)

with col3:
    st.metric("💰 Subventions", len(subv))

with col4:
    chauds = len(prospects_chauds) if not prospects_chauds.empty else 0
    st.metric("🔥 Prospects chauds", chauds)

st.markdown("---")

if not subv.empty:
    st.subheader("📊 Score des subventions")
    col_a, col_b = st.columns(2)
    with col_a:
        score_counts = subv["Score"].value_counts().sort_index()
        st.bar_chart(score_counts)
    with col_b:
        if "Region" in subv.columns:
            region_counts = subv["Region"].value_counts()
            st.bar_chart(region_counts)

if veille:
    st.subheader("📅 Événements à venir")
    for sheet_name, df in veille.items():
        if not df.empty and "score_strategique" in df.columns:
            top = df.nlargest(5, "score_strategique")[
                ["nom", "score_strategique", "lieu"]
            ]
            st.dataframe(top, width="stretch", hide_index=True)

if not prospects_chauds.empty:
    st.subheader("🏫 Top prospects")
    df_p = prospects_chauds.copy()
    if "score" in df_p.columns:
        if df_p["score"].dtype == object:
            df_p["score"] = pd.to_numeric(df_p["score"], errors="coerce")
        top_p = df_p.nlargest(5, "score")[["nom", "type", "localisation", "score"]]
        st.dataframe(top_p, width="stretch", hide_index=True)

st.markdown("---")
st.caption(f"Dernière mise à jour : {pd.Timestamp.now():%Y-%m-%d %H:%M}")
