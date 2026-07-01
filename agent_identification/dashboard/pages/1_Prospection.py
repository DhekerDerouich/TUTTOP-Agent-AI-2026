import streamlit as st
import pandas as pd
from pathlib import Path
import pandas as pd
from dashboard.utils.data_loader import (
    load_prospects,
    get_prospect_source_info,
    prospect_sources_available,
    PROSPECT_SOURCES,
)
from dashboard.utils.runner import run_pipeline


def _get_contacts_for_domaine(domaine: str) -> pd.DataFrame:
    path = Path(__file__).resolve().parent.parent.parent / "data" / "contacts.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str).fillna("")
    if "domaine" not in df.columns:
        return pd.DataFrame()
    return df[df["domaine"] == domaine].copy()


st.title("🏫 Prospection établissements")

tab1, tab2 = st.tabs(["🚀 Lancer", "📋 Résultats"])

with tab1:
    st.subheader("Lancer une prospection")

    col1, col2, col3 = st.columns(3)
    with col1:
        pays = st.selectbox("Pays", ["france", "tunisie", "belgique", "suisse"])
    with col2:
        statut = st.selectbox("Statut", ["Privé", "Public", None])
        statut = None if statut == "None" else statut
    with col3:
        limit = st.number_input(
            "Limite", min_value=100, max_value=50000, value=5000, step=500
        )

    quick = st.checkbox("Mode rapide (skip API/Web)")

    if st.button("▶️ Lancer la prospection", type="primary", use_container_width=True):
        if st.session_state.get("pipeline_running"):
            st.warning("Un pipeline est déjà en cours d'exécution")
        else:
            st.session_state.pipeline_running = True
            placeholder = st.empty()
            with placeholder.container():
                with st.status("Prospection en cours...", expanded=True) as status:
                    for line in run_pipeline(
                        "prospection",
                        pays=pays,
                        statut=statut,
                        limit=limit,
                        quick=quick,
                    ):
                        st.text(line)
                    status.update(label="Prospection terminée", state="complete")
            st.session_state.pipeline_running = False
            st.rerun()

with tab2:
    available = prospect_sources_available()
    if not available:
        st.info("Aucun fichier de prospection trouvé")
        st.stop()

    source_options = {
        PROSPECT_SOURCES[k]["label"]: k for k in available if k in PROSPECT_SOURCES
    }
    source_options["Dernier run pipeline"] = "run"

    selected_label = st.selectbox("Source de données", list(source_options.keys()))
    selected_key = source_options[selected_label]

    info = get_prospect_source_info(selected_key)
    has_data = info["rows"] > 0

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("Prospects", f"{info['rows']:,}".replace(",", " "))
    with col_info2:
        st.metric("Fichier", info["path"] if info["path"] else "—")
    with col_info3:
        st.metric(
            "Date", info["date"].strftime("%d/%m/%Y %H:%M") if info["date"] else "—"
        )

    if not has_data:
        st.info(f"Aucune donnée dans {selected_label}")
        st.stop()

    df = load_prospects(selected_key)
    if df.empty:
        st.info("Impossible de charger les données")
        st.stop()

    st.markdown("---")
    st.subheader("Filtres")

    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1, 1, 1, 1, 2])

    with col_f1:
        if "pays" in df.columns:
            pays_list = ["Tous"] + sorted(df["pays"].dropna().unique().tolist())
            selected_pays = st.selectbox("Pays", pays_list)
        else:
            selected_pays = "Tous"

    with col_f2:
        if "type" in df.columns:
            types = ["Tous"] + sorted(df["type"].dropna().unique().tolist())
            selected_type = st.selectbox("Type", types)
        else:
            selected_type = "Tous"

    with col_f3:
        if "score" in df.columns:
            scores = df["score"].dropna()
            if scores.dtype == object:
                scores = pd.to_numeric(scores, errors="coerce")
            min_s = float(scores.min()) if len(scores) else 0
            max_s = float(scores.max()) if len(scores) else 100
            score_range = st.slider(
                "Score min",
                int(min_s),
                int(max_s),
                int(min_s),
            )
        else:
            score_range = 0
            st.caption("Score non disponible")

    with col_f4:
        if "localisation" in df.columns:
            all_cities = sorted(df["localisation"].dropna().unique())
            selected_cities = st.multiselect(
                "Ville",
                all_cities,
                placeholder="Choisir ville(s)",
            )
        else:
            selected_cities = []

    with col_f5:
        search = st.text_input("🔍 Rechercher par nom", placeholder="Ex: Lycée...")

    exclude_default = "sport, agricole, hôtelier, restauration, mfr, musical"
    exclude_keywords = st.text_input(
        "🚫 Exclure (mots-clés dans le nom)",
        value=exclude_default,
        placeholder="sport, agricole, hôtelier",
        help="Séparés par des virgules. Exclut les établissements dont le nom contient ces mots.",
    )

    filtered = df.copy()

    if selected_pays != "Tous":
        filtered = filtered[filtered["pays"] == selected_pays]
    if selected_type != "Tous":
        filtered = filtered[filtered["type"] == selected_type]
    if "score" in filtered.columns:
        score_col = pd.to_numeric(filtered["score"], errors="coerce")
        filtered = filtered[score_col >= score_range]
    if selected_cities:
        filtered = filtered[filtered["localisation"].isin(selected_cities)]
    if search:
        filtered = filtered[filtered["nom"].str.contains(search, case=False, na=False)]
    if exclude_keywords:
        words = [w.strip().lower() for w in exclude_keywords.split(",") if w.strip()]
        if words:
            for w in words:
                filtered = filtered[
                    ~filtered["nom"].str.contains(w, case=False, na=False)
                ]

    st.caption(f"{len(filtered)} prospects après filtrage")

    display_cols = [
        c
        for c in ["nom", "type", "localisation", "site_web", "email", "score", "pays"]
        if c in filtered.columns
    ]
    st.dataframe(filtered[display_cols], width="stretch", hide_index=True)

    col_dl1, col_dl2, _ = st.columns([1, 1, 3])
    with col_dl1:
        csv_data = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Télécharger CSV",
            csv_data,
            "prospects.csv",
            use_container_width=True,
        )
    with col_dl2:
        try:
            import openpyxl
            from io import BytesIO

            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                filtered.to_excel(writer, index=False, sheet_name="Prospects")
            st.download_button(
                "📥 Télécharger XLSX",
                buf.getvalue(),
                "prospects.xlsx",
                use_container_width=True,
            )
        except ImportError:
            st.caption("openpyxl non installé pour l'export XLSX")

    st.markdown("---")
    st.subheader("🔍 Fiche prospect détaillée")

    search_fiche = st.text_input(
        "Rechercher un prospect par nom",
        placeholder="Tapez un nom pour afficher la fiche détaillée...",
    )

    if search_fiche:
        matches = filtered[
            filtered["nom"].str.contains(search_fiche, case=False, na=False)
        ]

        if matches.empty:
            st.info("Aucun prospect trouvé avec ce nom")
        else:
            seen = set()
            unique = []
            for _, r in matches.iterrows():
                k = r["nom"]
                if k not in seen:
                    seen.add(k)
                    unique.append((k, r.get("localisation", ""), r.get("pays", "")))

            if len(unique) == 1:
                selected = matches[matches["nom"] == unique[0][0]].iloc[0]
            else:
                labels = [
                    f"{n} — {l} ({p})" if l else f"{n} ({p})" for n, l, p in unique
                ]
                chosen = st.selectbox("Plusieurs prospects trouvés", labels)
                idx = labels.index(chosen)
                selected = matches[matches["nom"] == unique[idx][0]].iloc[0]

            # --- CARD ---
            score_raw = selected.get("score", "0")
            try:
                score_val = int(float(score_raw))
            except (ValueError, TypeError):
                score_val = 0

            if score_val >= 80:
                score_color = "#22c55e"
            elif score_val >= 50:
                score_color = "#f59e0b"
            else:
                score_color = "#ef4444"

            domaine = selected.get("domaine", "")
            contacts = _get_contacts_for_domaine(domaine) if domaine else pd.DataFrame()

            st.markdown(
                f"""
                <div style="border:1px solid #e5e7eb; border-radius:12px; padding:24px; background:#fafafa; margin-top:12px;">
                    <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px;">
                        <h3 style="margin:0; font-size:1.3rem;">{selected.get("nom", "")}</h3>
                        <span style="background:{score_color}; color:white; padding:3px 14px; border-radius:20px; font-weight:bold; font-size:0.85rem;">
                            Score {score_val}/100
                        </span>
                        <span style="background:#e0e7ff; color:#3730a3; padding:3px 14px; border-radius:20px; font-size:0.85rem;">
                            {selected.get("type", "—")}
                        </span>
                        <span style="background:#dbeafe; color:#1e40af; padding:3px 14px; border-radius:20px; font-size:0.85rem;">
                            {selected.get("pays", "—")}
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:12px;">
                        <div><strong>🌐 Site web</strong><br><a href="{selected.get("site_web", "#")}" target="_blank">{selected.get("site_web", "—")}</a></div>
                        <div><strong>📧 Email</strong><br>{selected.get("email", "—")}</div>
                        <div><strong>📞 Téléphone</strong><br>{selected.get("telephone", "—")}</div>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                        <div><strong>📍 Localisation</strong><br>{selected.get("localisation", "—")}</div>
                        <div><strong>🔗 Domaine</strong><br>{domaine if domaine else "—"}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander(f"👥 Contacts ({len(contacts)} trouvé(s))"):
                if contacts.empty:
                    st.info("Aucun contact trouvé pour cet établissement")
                else:
                    for _, c in contacts.iterrows():
                        cols = st.columns([1, 2, 2])
                        with cols[0]:
                            st.markdown(f"**{c.get('contact_nom', '?')}**")
                        with cols[1]:
                            st.markdown(f"*{c.get('contact_titre', '')}*")
                        with cols[2]:
                            link = c.get("linkedin_url", "")
                            email = c.get("email", "")
                            parts = []
                            if email:
                                parts.append(f"📧 {email}")
                            if link:
                                parts.append(f"[🔗 LinkedIn]({link})")
                            st.markdown("  ".join(parts) if parts else "—")
                        st.markdown(
                            "<hr style='margin:6px 0;'>", unsafe_allow_html=True
                        )
