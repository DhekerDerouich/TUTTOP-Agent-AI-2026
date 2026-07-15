import streamlit as st
import os

# Inject Streamlit secrets into os.environ for subprocesses and module imports
try:
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

st.set_page_config(
    page_title="TUT'TOP Agent Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.image(
    "https://img.icons8.com/fluency/96/artificial-intelligence.png",
    width=64,
)
st.sidebar.title("TUT'TOP")
st.sidebar.caption("Agent de prospection EdTech")

st.sidebar.markdown("---")
st.sidebar.markdown("### Pipelines")
st.sidebar.info(
    """
- **Prospection** : écoles privées/publiques
- **Veille** : hackathons + événements EdTech
- **Subventions** : aides et financements
- **Contacts** : recherche emails (RocketReach)
    """
)

if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "pipeline_output" not in st.session_state:
    st.session_state.pipeline_output = []

dashboard = st.Page(
    "dashboard/pages/4_Tableau_de_bord.py", title="Tableau de bord", icon="📊"
)
prospection = st.Page(
    "dashboard/pages/1_Prospection.py", title="Prospection", icon="🏫"
)
veille = st.Page("dashboard/pages/2_Veille.py", title="Veille", icon="📅")
subventions = st.Page(
    "dashboard/pages/3_Subventions.py", title="Subventions", icon="💰"
)
contacts = st.Page("dashboard/pages/5_Contacts.py", title="Contacts", icon="🔍")

pg = st.navigation([dashboard, prospection, veille, subventions, contacts])
pg.run()
