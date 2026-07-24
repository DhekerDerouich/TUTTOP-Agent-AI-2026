import streamlit as st
import pandas as pd
import os
import base64
import json
from pathlib import Path
from datetime import datetime, date, timedelta

import requests

from agent.rocketreach_client import (
    RocketReachClient,
    extract_person_info,
    extract_company_info,
    DAILY_LIMIT,
    COMPANY_DAILY_LIMIT,
)

DATA = Path(__file__).resolve().parent.parent.parent / "data"
HISTORY_FILE = DATA / "contacts_rocketreach.csv"

# ---- GitHub sync (permanent storage across restarts) ----


def _github_repo() -> tuple[str, str] | None:
    """Get GitHub owner/repo from git remote or env."""
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        return None
    try:
        import subprocess

        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        url = r.stdout.strip()
        # https://github.com/owner/repo.git  or  git@github.com:owner/repo.git
        url = url.replace("https://github.com/", "").replace("git@github.com:", "")
        url = url.rstrip(".git")
        parts = url.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None


def _load_from_github() -> pd.DataFrame | None:
    """Fetch contacts CSV from GitHub repo via API."""
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        return None
    repo = _github_repo()
    if not repo:
        return None
    owner, repo_name = repo
    path = "agent_identification/data/contacts_rocketreach.csv"
    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            from io import StringIO

            df = pd.read_csv(StringIO(content), dtype=str).fillna("")
            return df
    except Exception:
        pass
    return None


def _sync_to_github(df: pd.DataFrame):
    """Push CSV to GitHub repo via API (silent, best-effort)."""
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        return
    repo = _github_repo()
    if not repo:
        return
    owner, repo_name = repo
    path = "agent_identification/data/contacts_rocketreach.csv"
    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"

    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8")
    content_b64 = base64.b64encode(csv_bytes).decode("utf-8")

    # Get SHA of existing file if it exists
    sha = None
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code == 200:
            sha = resp.json().get("sha")
    except Exception:
        pass

    payload = {
        "message": f"Sync contacts ({len(df)} rows)",
        "content": content_b64,
    }
    if sha:
        payload["sha"] = sha

    try:
        requests.put(
            url, headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=15
        )
    except Exception:
        pass


# ---- Local history load/save ----


def _load_history() -> pd.DataFrame:
    if "contacts_history" in st.session_state:
        return st.session_state.contacts_history

    # Try GitHub first (persists across restarts)
    gh = _load_from_github()
    if gh is not None and not gh.empty:
        st.session_state.contacts_history = gh
        # Also save locally for backup
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            gh.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
        except Exception:
            pass
        return gh

    # Fallback to local CSV
    if HISTORY_FILE.exists():
        df = pd.read_csv(HISTORY_FILE, dtype=str).fillna("")
        st.session_state.contacts_history = df
        return df

    empty = pd.DataFrame()
    st.session_state.contacts_history = empty
    return empty


def _save_history(df: pd.DataFrame):
    st.session_state.contacts_history = df
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass
    # Also sync to GitHub for permanent storage
    _sync_to_github(df)


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

    # Ensure all columns exist in hist (migration-safe)
    for col in new_row:
        if col not in hist.columns:
            hist[col] = ""

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

# ---- Header: quota info + GitHub status ----
remaining = rr.remaining
used = rr.used_today
co_remaining = rr.company_remaining
co_used = rr.company_used_today

col_q1, col_q2 = st.columns(2)
with col_q1:
    if remaining <= 5:
        st.error(f"⚠️ Person search: {remaining}/{DAILY_LIMIT} restants")
    elif remaining <= 15:
        st.warning(f"⚡ Person search: {remaining}/{DAILY_LIMIT} restants")
    else:
        st.info(f"✅ Person search: {remaining}/{DAILY_LIMIT} restants")
with col_q2:
    if co_remaining <= 5:
        st.error(f"⚠️ Company export: {co_remaining}/{COMPANY_DAILY_LIMIT} restants")
    elif co_remaining <= 20:
        st.warning(f"⚡ Company export: {co_remaining}/{COMPANY_DAILY_LIMIT} restants")
    else:
        st.info(f"✅ Company export: {co_remaining}/{COMPANY_DAILY_LIMIT} restants")

gh_token = os.environ.get("GITHUB_TOKEN") or ""
if gh_token and _github_repo():
    st.caption(
        "💾 Sauvegarde GitHub activée — l'historique est conservé entre les sessions"
    )
else:
    st.caption(
        "ℹ️ Ajoute GITHUB_TOKEN dans Settings → Secrets pour sauvegarder l'historique en permanence"
    )

tab_search, tab_company, tab_history = st.tabs(
    ["🔍 Recherche", "🏢 Entreprises", "📋 Historique"]
)

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
# TAB 2 : ENTREPRISES
# ==============================
with tab_company:
    st.subheader("Recherche d'entreprises")
    st.caption("Recherche gratuite · Lookup = 1 crédit company_export")

    # Quota info
    if rr.company_remaining <= 5:
        st.error(
            f"⚠️ {rr.company_remaining}/{COMPANY_DAILY_LIMIT} crédits company restants"
        )
    elif rr.company_remaining <= 20:
        st.warning(
            f"⚡ {rr.company_remaining}/{COMPANY_DAILY_LIMIT} crédits company restants"
        )
    else:
        st.info(
            f"✅ {rr.company_remaining}/{COMPANY_DAILY_LIMIT} crédits company restants"
        )

    co_col1, co_col2 = st.columns(2)
    with co_col1:
        co_name = st.text_input(
            "Nom entreprise", placeholder="Acme Corp", key="co_name"
        )
        co_domain = st.text_input("Domaine", placeholder="acme.com", key="co_domain")
    with co_col2:
        co_industry = st.text_input(
            "Industrie", placeholder="Education", key="co_industry"
        )
        co_location = st.text_input(
            "Localisation", placeholder="Paris, France", key="co_location"
        )

    if st.button(
        "🔍 Chercher entreprises",
        type="primary",
        use_container_width=True,
        key="btn_co_search",
    ):
        if not co_name and not co_domain:
            st.warning("Entre au moins un nom ou un domaine")
        else:
            with st.spinner("Recherche d'entreprises..."):
                co_result = rr.search_company(
                    name=co_name.strip(),
                    domain=co_domain.strip(),
                    industry=co_industry.strip(),
                    location=co_location.strip(),
                )

            if "error" in co_result:
                st.error(f"❌ {co_result['error']}")
            else:
                companies = co_result.get("accounts") or co_result.get("results") or []
                if not companies:
                    st.warning("Aucune entreprise trouvée pour ces critères.")
                else:
                    st.success(f"🔍 {len(companies)} entreprise(s) trouvée(s)")
                    st.caption(
                        "Clique sur « Voir détails » pour obtenir les infos complètes (1 crédit)"
                    )

                    for i, c in enumerate(companies[:10]):
                        c_name = c.get("name", "?")
                        c_domain = c.get("domain", "")
                        c_industry = c.get("industry", "")
                        c_size = c.get("estimated_num_employees", "")
                        c_location = c.get("location", "")
                        c_linkedin = c.get("linkedin_url", "")
                        c_id = c.get("id")

                        label = f"**{c_name}**"
                        if c_domain:
                            label += f" · {c_domain}"
                        if c_industry:
                            label += f" · {c_industry}"
                        if c_size:
                            label += f" · {c_size} employés"
                        if c_location:
                            label += f" · {c_location}"

                        with st.container(border=True):
                            st.markdown(label)
                            if c_linkedin:
                                st.caption(f"[🔗 LinkedIn]({c_linkedin})")

                            if st.button(
                                "📋 Voir détails", key=f"co_detail_{i}_{c_id}"
                            ):
                                with st.spinner(
                                    "Récupération des détails... (1 crédit)"
                                ):
                                    if c_domain:
                                        raw_co = rr.lookup_company_by_domain(c_domain)
                                    elif c_name:
                                        raw_co = rr.lookup_company_by_name(c_name)
                                    else:
                                        raw_co = {"error": "Pas de domaine ni nom"}

                                info_co = extract_company_info(raw_co)

                                if "error" in info_co:
                                    st.error(f"❌ {info_co['error']}")
                                else:
                                    st.success(
                                        "✅ Détails récupérés"
                                        + (" (cache)" if info_co.get("_cached") else "")
                                    )
                                    with st.container(border=True):
                                        st.markdown(f"### {info_co['name']}")
                                        if info_co["domain"]:
                                            st.caption(f"🌐 {info_co['domain']}")
                                        if info_co["industry"]:
                                            st.caption(f"🏭 {info_co['industry']}")
                                        if info_co["size"]:
                                            st.caption(f"👥 {info_co['size']} employés")
                                        if info_co["revenue"]:
                                            st.caption(f"💰 {info_co['revenue']}")
                                        if info_co["location"]:
                                            st.caption(f"📍 {info_co['location']}")
                                        if info_co["founded_year"]:
                                            st.caption(
                                                f"📅 Fondée en {info_co['founded_year']}"
                                            )
                                        if info_co["linkedin_url"]:
                                            st.markdown(
                                                f"[🔗 LinkedIn]({info_co['linkedin_url']})"
                                            )
                                        if info_co["description"]:
                                            st.markdown("---")
                                            st.markdown(info_co["description"])

                                    # Save to history
                                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                                    today_str = date.today().isoformat()
                                    hist = _load_history()
                                    new_row = {
                                        "name": info_co["name"],
                                        "title": "",
                                        "company": info_co["name"],
                                        "location": info_co["location"],
                                        "email": "",
                                        "has_email": "Non",
                                        "linkedin_url": info_co["linkedin_url"],
                                        "search_mode": "company_lookup",
                                        "found_at": now,
                                        "found_date": today_str,
                                    }
                                    for col in new_row:
                                        if col not in hist.columns:
                                            hist[col] = ""
                                    hist = pd.concat(
                                        [hist, pd.DataFrame([new_row])],
                                        ignore_index=True,
                                    )
                                    _save_history(hist)
                                    st.success(
                                        "💾 Entreprise sauvegardée dans l'historique"
                                    )

# ==============================
# TAB 3 : HISTORIQUE
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
