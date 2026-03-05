import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="SODEXAM", layout="wide")

# --- CONNEXION ---
# On utilise une méthode de lecture plus simple
conn = st.connection("gsheets", type=GSheetsConnection)

def charger_donnees(nom_onglet):
    # Cette fonction va tenter de lire l'onglet par son nom
    return conn.read(worksheet=nom_onglet, ttl="0")

# --- AUTHENTIFICATION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False

if not st.session_state.connecte:
    st.title("🔐 Connexion SODEXAM")
    
    with st.form("login"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        bouton = st.form_submit_button("Se connecter")
        
        if bouton:
            try:
                # Tentative de lecture de l'onglet utilisateurs
                users = charger_donnees("utilisateurs")
                
                # Vérification
                user_match = users[(users['username'].astype(str) == str(u)) & (users['password'].astype(str) == str(p))]
                
                if not user_match.empty:
                    st.session_state.connecte = True
                    st.session_state.user_ville = user_match.iloc[0]['ville']
                    st.session_state.user_role = user_match.iloc[0]['role']
                    st.success("Connecté !")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error(f"Erreur de connexion au Google Sheet.")
                st.info("Vérifiez que l'onglet s'appelle bien 'utilisateurs' et que le partage est public.")
                # Affichage de l'erreur brute pour comprendre
                st.exception(e)

else:
    # --- INTERFACE UNE FOIS CONNECTÉ ---
    st.sidebar.title("SODEXAM")
    st.sidebar.write(f"Station : {st.session_state.user_ville}")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()
        
    st.header(f"Tableau de bord - {st.session_state.user_ville}")
    
    try:
        df = charger_donnees("relevés")
        st.dataframe(df)
    except:
        st.error("Impossible de charger les relevés.")
