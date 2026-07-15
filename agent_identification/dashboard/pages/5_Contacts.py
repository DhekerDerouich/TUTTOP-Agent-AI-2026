import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta

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


def _save_search(info: dict, search_mode: str):
    """Save a search result to history. Always saves, even without email."""
    hist = _load_history()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today_str = date.today().isoformat()

    email_str = "; ".join(e["email"] for e in info.get("emails", []) if e["email"])

    new_row = {
        "name": info.get("name", ""),
        "title": info.get("title", ""),
        "company": info.get("company", ""),
        "location": info.get("location", ""),
        "email": email_str,
        "has_email": "Oui" if email_str else "Non",
        "linkedin_url": info.get("linkedin_url", ""),
        "search_mode": search_mode,
        "found_at": now,
        "found_date": today_str,
    }

    # Dedup by linkedin_url or name+company
    dup = False
    if new_row["linkedin_url"]:
        dup = not hist[hist["linkedin_url"] == new_row["linkedin_url"]].empty
    elif new_row["name"]:
        dup = not hist[
            (hist["name"] == new_row["name"]) & (hist["company"] == new_row["company"])
        ].empty

    if dup:
        st.info("📌 Déjà dans l'historique")
        return

    hist = pd.concat([hist, pd.DataFrame([new_row])], ignore_index=True)
    _save_history(hist)
    st.success("💾 Contact sauvegardé dans l'historique")


def _display_person(info: dict):
    """Display person details. Returns the info dict."""
    if "error" in info:
        st.error(f"❌ {info['error']}")
        return info

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

    return info


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

                info = _display_person(info)
                if info.get("name"):
                    _save_search(info, "LinkedIn URL")

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

                                        info = _display_person(info)
                                        if info.get("name"):
                                            _save_search(info, "Nom+Établissement")
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
        # ---- Date filter ----
        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            date_filter = st.radio(
                "Période",
                ["Tous", "Aujourd'hui", "Hier", "7 jours", "Date précise"],
                horizontal=True,
            )
        with col_f2:
            if date_filter == "Date précise":
                pick = st.date_input("Choisir une date", value=date.today())
                filter_date = pick.isoformat()
            elif date_filter == "Aujourd'hui":
                filter_date = date.today().isoformat()
            elif date_filter == "Hier":
                filter_date = (date.today() - timedelta(days=1)).isoformat()
            elif date_filter == "7 jours":
                filter_date = (date.today() - timedelta(days=7)).isoformat()
            else:
                filter_date = ""

        if filter_date and date_filter == "7 jours":
            cutoff = (date.today() - timedelta(days=7)).isoformat()
            filtered = hist[hist["found_date"] >= cutoff]
        elif filter_date:
            filtered = hist[hist["found_date"] == filter_date]
        else:
            filtered = hist

        # ---- Email filter ----
        email_filter = st.radio(
            "Email",
            ["Tous", "Avec email", "Sans email"],
            horizontal=True,
        )
        if email_filter == "Avec email":
            filtered = filtered[filtered["has_email"] == "Oui"]
        elif email_filter == "Sans email":
            filtered = filtered[filtered["has_email"] == "Non"]

        st.caption(f"{len(filtered)} contact(s) sur {len(hist)} au total")

        if filtered.empty:
            st.info("Aucun contact pour cette période")
        else:
            cols_hist = st.multiselect(
                "Colonnes à afficher",
                list(filtered.columns),
                default=[
                    c
                    for c in [
                        "name",
                        "title",
                        "company",
                        "email",
                        "has_email",
                        "location",
                        "found_date",
                    ]
                    if c in filtered.columns
                ],
            )
            if cols_hist:
                st.dataframe(
                    filtered[cols_hist], hide_index=True, use_container_width=True
                )

            csv = filtered.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "📥 Télécharger ce filtre (CSV)",
                csv,
                "contacts_rocketreach.csv",
            )

        if st.button("🗑️ Vider tout l'historique", type="secondary"):
            _save_history(pd.DataFrame())
            st.rerun()
