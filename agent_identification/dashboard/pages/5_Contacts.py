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


def _display_person(info: dict):
    if "error" in info:
        st.error(f"❌ {info['error']}")
        return

    st.success(
        "✅ Contact trouvé" + (" (depuis le cache)" if info.get("_cached") else "")
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
            st.markdown("**Emails**")
            df_emails = pd.DataFrame(info["emails"])
            df_emails["validation"] = df_emails["validation"].apply(
                lambda v: {
                    "valid": "✅",
                    "invalid": "❌",
                    "accept-all": "⚠️",
                    "unknown": "❓",
                }.get(v, v)
            )
            st.dataframe(df_emails, hide_index=True, use_container_width=True)
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

    return info.get("name") and len(info.get("emails", [])) > 0


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

    if mode == "LinkedIn URL":
        linkedin_url = st.text_input(
            "URL du profil LinkedIn",
            placeholder="https://www.linkedin.com/in/...",
            help="Colle l'URL complète du profil LinkedIn",
        )

        if st.button("🔍 Chercher", type="primary", use_container_width=True):
            if not linkedin_url:
                st.warning("Entre une URL LinkedIn")
            else:
                with st.spinner("Recherche en cours... (1 crédit)"):
                    raw = rr.lookup_by_linkedin(linkedin_url.strip())
                    info = extract_person_info(raw)

                found = _display_person(info)
                if found:
                    # Auto-save
                    hist = _load_history()
                    email_str = "; ".join(
                        e["email"] for e in info.get("emails", []) if e["email"]
                    )
                    if email_str and not hist[hist["email"] == email_str].empty:
                        st.info("📌 Déjà dans l'historique")
                    else:
                        new_row = {
                            "name": info["name"],
                            "title": info.get("title", ""),
                            "company": info.get("company", ""),
                            "location": info.get("location", ""),
                            "email": email_str,
                            "linkedin_url": info.get("linkedin_url", ""),
                            "found_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                        hist = pd.concat(
                            [hist, pd.DataFrame([new_row])], ignore_index=True
                        )
                        _save_history(hist)
                        st.success("💾 Contact sauvegardé dans l'historique")

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

        if st.button("🔍 Chercher", type="primary", use_container_width=True):
            if not name:
                st.warning("Entre au moins un nom")
            else:
                # Step 1: Search (free)
                with st.spinner("Recherche de profils..."):
                    search_result = rr.search_person(
                        name=name.strip(),
                        company=company.strip(),
                        title=title.strip(),
                        location=location.strip(),
                    )

                if "error" in search_result:
                    st.error(f"❌ {search_result['error']}")
                else:
                    profiles = (
                        search_result.get("profiles")
                        or search_result.get("results")
                        or []
                    )
                    if not profiles:
                        st.warning("Aucun profil trouvé pour ces critères.")
                    else:
                        st.success(f"🔍 {len(profiles)} profil(s) trouvé(s)")
                        st.caption(
                            "Sélectionne un profil pour voir ses coordonnées (1 crédit)"
                        )

                        for i, p in enumerate(profiles[:10]):
                            p_name = p.get("name", "?")
                            p_title = p.get("current_title", "")
                            p_company = p.get("current_employer", "") or (
                                p.get("current_company") or {}
                            ).get("name", "")
                            p_location = p.get("location", "")
                            p_linkedin = p.get("linkedin_url", "")
                            p_id = p.get("id") or p.get("profile_id")

                            label = f"**{p_name}**"
                            if p_title:
                                label += f" — {p_title}"
                            if p_company:
                                label += f" @ {p_company}"
                            if p_location:
                                label += f" · {p_location}"

                            with st.container(border=True):
                                st.markdown(label)
                                if p_linkedin:
                                    st.caption(f"[🔗 LinkedIn]({p_linkedin})")
                                if p_id:
                                    if st.button(
                                        f"🔍 Voir coordonnées", key=f"select_{i}_{p_id}"
                                    ):
                                        with st.spinner(
                                            "Récupération des coordonnées... (1 crédit)"
                                        ):
                                            raw = rr.lookup_by_id(p_id)
                                            info = extract_person_info(raw)

                                        found = _display_person(info)
                                        if found:
                                            hist = _load_history()
                                            email_str = "; ".join(
                                                e["email"]
                                                for e in info.get("emails", [])
                                                if e["email"]
                                            )
                                            if (
                                                email_str
                                                and not hist[
                                                    hist["email"] == email_str
                                                ].empty
                                            ):
                                                st.info("📌 Déjà dans l'historique")
                                            else:
                                                new_row = {
                                                    "name": info["name"],
                                                    "title": info.get("title", ""),
                                                    "company": info.get("company", ""),
                                                    "location": info.get(
                                                        "location", ""
                                                    ),
                                                    "email": email_str,
                                                    "linkedin_url": info.get(
                                                        "linkedin_url", ""
                                                    ),
                                                    "found_at": datetime.now().strftime(
                                                        "%Y-%m-%d %H:%M"
                                                    ),
                                                }
                                                hist = pd.concat(
                                                    [hist, pd.DataFrame([new_row])],
                                                    ignore_index=True,
                                                )
                                                _save_history(hist)
                                                st.success(
                                                    "💾 Contact sauvegardé dans l'historique"
                                                )
                                else:
                                    st.caption(
                                        "⚠️ Pas d'ID — impossible de récupérer les coordonnées"
                                    )

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
