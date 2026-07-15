import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from agent.rocketreach_client import (
    RocketReachClient,
    extract_person_info,
    DAILY_LIMIT,
)

DATA = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_FILE = DATA / "contacts_rocketreach.csv"


def _load_history() -> pd.DataFrame:
    if HISTORY_FILE.exists():
        df = pd.read_csv(HISTORY_FILE, dtype=str).fillna("")
        return df
    return pd.DataFrame()


def _save_history(df: pd.DataFrame):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")


st.title("🔍 Recherche de contacts RocketReach")

rr = RocketReachClient()

# ---- Header: quota info ----
remaining = rr.remaining
used = rr.used_today
if remaining <= 5:
    st.error(f"⚠️ {remaining}/{DAILY_LIMIT} requêtes restantes aujourd'hui")
elif remaining <= 15:
    st.warning(f"⚡ {remaining}/{DAILY_LIMIT} requêtes restantes aujourd'hui")
else:
    st.info(f"✅ {remaining}/{DAILY_LIMIT} requêtes restantes aujourd'hui")

tab_search, tab_history = st.tabs(["🔍 Recherche", "📋 Historique"])

# ==============================
# TAB 1 : RECHERCHE
# ==============================
with tab_search:
    mode = st.radio(
        "Mode de recherche",
        ["LinkedIn URL", "Nom + Établissement"],
        horizontal=True,
    )

    linkedin_url = ""
    name = ""
    company = ""
    location = ""
    title = ""

    if mode == "LinkedIn URL":
        linkedin_url = st.text_input(
            "URL du profil LinkedIn",
            placeholder="https://www.linkedin.com/in/...",
            help="Colle l'URL complète du profil LinkedIn",
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nom complet *", placeholder="Jean Dupont")
        with col2:
            title = st.text_input("Titre / Poste", placeholder="Directeur IT")
        col3, col4 = st.columns(2)
        with col3:
            company = st.text_input(
                "Entreprise / Établissement", placeholder="Acme Corp"
            )
        with col4:
            location = st.text_input("Localisation", placeholder="Nice, France")

    col_save = st.columns([1, 3])[0]
    auto_save = col_save.checkbox("Sauvegarder automatiquement", value=True)

    if st.button("🔍 Chercher", type="primary", use_container_width=True):
        if mode == "LinkedIn URL" and not linkedin_url:
            st.warning("Entre une URL LinkedIn")
        elif mode == "Nom + Établissement" and not name:
            st.warning("Entre au moins un nom")
        else:
            with st.spinner("Recherche en cours..."):
                if mode == "LinkedIn URL":
                    raw = rr.lookup_by_linkedin(linkedin_url.strip())
                else:
                    raw = rr.lookup_by_name_company(
                        name=name.strip(),
                        company=company.strip(),
                        location=location.strip(),
                        title=title.strip(),
                    )

                info = extract_person_info(raw)

            if "error" in info:
                st.error(f"❌ {info['error']}")
            else:
                st.success(
                    "✅ Contact trouvé"
                    + (" (depuis le cache)" if info.get("_cached") else "")
                )

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### {info['name'] or '?'}")
                        if info["title"]:
                            st.caption(f"**{info['title']}**")
                        if info["company"]:
                            st.caption(f"🏢 {info['company']}")
                        if info["location"]:
                            st.caption(f"📍 {info['location']}")
                    with c2:
                        if info["linkedin_url"]:
                            st.markdown(f"[🔗 LinkedIn]({info['linkedin_url']})")

                    if info["emails"]:
                        st.markdown("---")
                        df_emails = pd.DataFrame(info["emails"])
                        st.dataframe(
                            df_emails, hide_index=True, use_container_width=True
                        )
                    else:
                        st.info("Aucun email trouvé")

                    if info["phones"]:
                        with st.expander("📞 Téléphones"):
                            for p in info["phones"]:
                                st.text(f"{p['phone']} ({p['type']})")

                    if info["work_history"]:
                        with st.expander("💼 Expériences"):
                            for w in info["work_history"]:
                                st.markdown(
                                    f"- **{w['title']}** chez {w['company']} ({w['start']} – {w['end']})"
                                )

                    if info.get("skills"):
                        with st.expander("🧠 Compétences"):
                            st.write(", ".join(info["skills"]))

                    if info.get("education"):
                        with st.expander("🎓 Formation"):
                            for edu in info["education"]:
                                if isinstance(edu, dict):
                                    st.markdown(
                                        f"- {edu.get('school', '')} — {edu.get('degree', '')} ({edu.get('major', '')})"
                                    )
                                else:
                                    st.text(str(edu))

                # ---- Auto-save ----
                if auto_save and info.get("name"):
                    hist = _load_history()
                    emails_str = "; ".join(
                        e["email"] for e in info.get("emails", []) if e["email"]
                    )
                    if emails_str and not hist[hist["email"] == emails_str].empty:
                        st.info("📌 Déjà dans l'historique")
                    elif emails_str:
                        new_row = {
                            "name": info["name"],
                            "title": info.get("title", ""),
                            "company": info.get("company", ""),
                            "location": info.get("location", ""),
                            "email": emails_str,
                            "linkedin_url": info.get("linkedin_url", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                        hist = pd.concat(
                            [hist, pd.DataFrame([new_row])], ignore_index=True
                        )
                        _save_history(hist)
                        st.success("💾 Contact sauvegardé dans l'historique")

# ==============================
# TAB 2 : HISTORIQUE
# ==============================
with tab_history:
    st.subheader("Contacts déjà trouvés")
    hist = _load_history()

    if hist.empty:
        st.info("Aucun contact sauvegardé pour l'instant")
    else:
        st.caption(f"{len(hist)} contact(s) au total")
        cols_hist = st.multiselect(
            "Colonnes à afficher",
            list(hist.columns),
            default=[
                c
                for c in ["name", "title", "company", "email", "location"]
                if c in hist.columns
            ],
        )
        if cols_hist:
            st.dataframe(hist[cols_hist], hide_index=True, use_container_width=True)

        csv = hist.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📥 Télécharger (CSV)",
            csv,
            "contacts_rocketreach.csv",
        )

        if st.button("🗑️ Vider l'historique", type="secondary"):
            _save_history(pd.DataFrame())
            st.rerun()
