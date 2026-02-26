import streamlit as st
import pandas as pd
import os
import io
import base64
import smtplib
import folium
from datetime import datetime
from streamlit_folium import st_folium
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# ==========================================
# 1. CONFIGURATION & FICHIERS
# ==========================================
FOLDER_DATA = "Donnees_Villes"
DB_USERS = "utilisateurs.csv"
LOGO_NOM = "logo_sodexam.png.png"

# --- PARAMÈTRES EMAIL (À MODIFIER AVEC TON CODE GOOGLE) ---
EMAIL_EXPEDITEUR = "votre_email@gmail.com"
MOT_DE_PASSE = "xxxx xxxx xxxx xxxx" 
EMAIL_DESTINATAIRE = "lateseraphinkone@gmail.com"

# Coordonnées réelles des stations SODEXAM
VILLES_COORDS = {
    "abidjan": [5.3600, -4.0083],
    "abengourou": [6.7300, -3.5000],
    "yamoussoukro": [6.8161, -5.2742],
    "bouake": [7.6897, -5.0303],
    "korhogo": [9.4580, -5.6295],
    "san-pedro": [4.7485, -6.6363],
    "man": [7.4125, -7.5538],
    "daoukro": [7.0591, -3.9631],
    "ouele": [7.1000, -3.5833],
    "daloa": [6.8773, -6.4502],
    "odienne": [9.5051, -7.5643]
}

if not os.path.exists(FOLDER_DATA): os.makedirs(FOLDER_DATA)

if not os.path.exists(DB_USERS):
    df_u = pd.DataFrame([{'login': 'admin', 'password': 'admin123', 'role': 'admin', 'ville': 'TOUTES'}])
    df_u.to_csv(DB_USERS, index=False)

# ==========================================
# 2. FONCTIONS TECHNIQUES
# ==========================================
def get_base64(file):
    if os.path.exists(file):
        with open(file, 'rb') as f: return base64.b64encode(f.read()).decode()
    return None

def charger_donnees_ville(ville):
    chemin = os.path.join(FOLDER_DATA, f"{ville.upper()}_data.csv")
    if not os.path.exists(chemin):
        return pd.DataFrame(columns=['Date', 'Heure', 'Ville', 'Pluie_mm', 'Orage', 'Eclair'])
    return pd.read_csv(chemin)

def charger_toutes_villes():
    fichiers = [f for f in os.listdir(FOLDER_DATA) if f.endswith(".csv")]
    all_dfs = []
    for f in fichiers:
        try:
            df_temp = pd.read_csv(os.path.join(FOLDER_DATA, f))
            if not df_temp.empty: all_dfs.append(df_temp)
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# ==========================================
# 3. INTERFACE & AUTHENTIFICATION
# ==========================================
st.set_page_config(page_title="SODEXAM - Gestion Pluvio", layout="wide")

if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Connexion SODEXAM")
    with st.form("login_form"):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter"):
            df_u = pd.read_csv(DB_USERS)
            user_row = df_u[(df_u['login'] == u) & (df_u['password'] == p)]
            if not user_row.empty:
                st.session_state.auth = True
                st.session_state.user = u
                st.session_state.role = user_row.iloc[0]['role']
                st.session_state.ville_user = user_row.iloc[0]['ville']
                st.rerun()
            else: st.error("Identifiants incorrects.")
    st.stop()

# ==========================================
# 4. BARRE LATÉRALE
# ==========================================
with st.sidebar:
    logo_b64 = get_base64(LOGO_NOM)
    if logo_b64:
        st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_b64}" width="150"></div>', unsafe_allow_html=True)
    
    st.title("Navigation")
    if st.session_state.role == 'admin':
        menu = st.radio("Aller vers :", ["🌍 Carte de Côte d'Ivoire", "✍️ Saisie des Relevés", "👥 Gestion des Comptes", "🛠️ Nettoyage des Tests"])
    else:
        menu = "✍️ Saisie des Relevés"

    if st.button("🚪 Déconnexion"):
        st.session_state.auth = False
        st.rerun()

# ==========================================
# 5. LOGIQUE DES MENUS
# ==========================================

# --- MENU : CARTE NATIONALE ---
if menu == "🌍 Carte de Côte d'Ivoire":
    st.header("📊 Situation Pluviométrique Nationale")
    df_total = charger_toutes_villes()
    
    if not df_total.empty:
        df_total['Date'] = pd.to_datetime(df_total['Date'], dayfirst=True)
        dates_dispo = sorted(df_total['Date'].dt.date.unique(), reverse=True)
        date_sel = st.selectbox("📅 Sélectionner la date à afficher", dates_dispo)
        
        df_jour = df_total[df_total['Date'].dt.date == date_sel]
        
        # Création de la carte
        m = folium.Map(location=[7.54, -5.55], zoom_start=7, tiles="OpenStreetMap")
        
        for _, row in df_jour.iterrows():
            ville_nom = str(row['Ville']).lower().strip()
            pluie = row['Pluie_mm']
            orage = "⚡ Oui" if row['Orage'] == 1 else "Non"
            
            if ville_nom in VILLES_COORDS:
                coord = VILLES_COORDS[ville_nom]
                # Couleur selon intensité
                couleur = "red" if pluie > 20 else "blue" if pluie > 0 else "green"
                
                folium.CircleMarker(
                    location=coord,
                    radius=8 + (pluie/5),
                    popup=f"<b>{ville_nom.upper()}</b><br>Pluie: {pluie}mm<br>Orage: {orage}",
                    color=couleur,
                    fill=True,
                    fill_opacity=0.7
                ).add_to(m)
        
        st_folium(m, width=1000, height=600)
        st.info("🟢 Vert: Sec | 🔵 Bleu: Pluie | 🔴 Rouge: Forte Pluie (>20mm)")
    else:
        st.warning("Aucune donnée enregistrée pour le moment.")

# --- MENU : SAISIE & RAPPORTS ---
elif menu == "✍️ Saisie des Relevés":
    v_user = st.session_state.ville_user
    if st.session_state.role == 'admin':
        v_user = st.selectbox("Vérifier la ville de :", list(VILLES_COORDS.keys()))

    st.header(f"📍 Station : {v_user.upper()}")
    
    # Formulaire de saisie
    with st.expander("➕ Enregistrer un nouveau relevé", expanded=True):
        with st.form("pluvio_form"):
            col1, col2 = st.columns(2)
            d = col1.date_input("Date du relevé")
            h = col2.selectbox("Heure", ["08:00", "18:00", "Cumul 24h"])
            p = col1.number_input("Précipitations (mm)", min_value=0.0, step=0.1)
            o = col2.checkbox("Présence d'Orage")
            e = col2.checkbox("Présence d'Éclairs")
            
            if st.form_submit_button("✅ Valider et Enregistrer"):
                df_v = charger_donnees_ville(v_user)
                nouveau = pd.DataFrame([{
                    'Date': d.strftime("%d/%m/%Y"), 'Heure': h, 'Ville': v_user.upper(),
                    'Pluie_mm': p, 'Orage': 1 if o else 0, 'Eclair': 1 if e else 0
                }])
                chemin = os.path.join(FOLDER_DATA, f"{v_user.upper()}_data.csv")
                nouveau.to_csv(chemin, mode='a', header=not os.path.exists(chemin), index=False)
                st.success("Donnée enregistrée en local !")
                st.rerun()

    # Affichage du tableau local
    df_v = charger_donnees_ville(v_user)
    if not df_v.empty:
        st.subheader("Historique des relevés")
        st.dataframe(df_v, use_container_width=True)
        
        # Bouton Mail
        if st.button("📧 Envoyer ce rapport à la Direction"):
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer: df_v.to_excel(writer, index=False)
                msg = MIMEMultipart()
                msg['Subject'] = f"PLUVIO SODEXAM - {v_user.upper()} - {datetime.now().strftime('%d/%m/%Y')}"
                msg.attach(MIMEText(f"Veuillez trouver ci-joint le relevé pour la station de {v_user}."))
                part = MIMEApplication(buf.getvalue(), Name=f"Releve_{v_user}.xlsx")
                part['Content-Disposition'] = f'attachment; filename="Releve_{v_user}.xlsx"'
                msg.attach(part)
                # Connexion SMTP (A configurer avec tes accès)
                st.info("Configuration SMTP requise pour l'envoi réel.")
            except Exception as ex: st.error(f"Erreur : {ex}")

# --- MENU : GESTION ADMIN ---
elif menu == "👥 Gestion des Comptes":
    st.header("⚙️ Administration des accès")
    df_u = pd.read_csv(DB_USERS)
    st.dataframe(df_u)
    
    with st.form("add_user"):
        st.write("Ajouter un agent")
        nl = st.text_input("Identifiant (ex: agent_man)")
        np = st.text_input("Mot de passe")
        nv = st.selectbox("Ville assignée", list(VILLES_COORDS.keys()))
        if st.form_submit_button("Créer le compte"):
            new_u = pd.DataFrame([{'login': nl, 'password': np, 'role': 'user', 'ville': nv.upper()}])
            pd.concat([df_u, new_u]).to_csv(DB_USERS, index=False)
            st.success("Compte créé !") ; st.rerun()

elif menu == "🛠️ Nettoyage des Tests":
    st.header("🛠️ Suppression des données de test")
    v_clean = st.selectbox("Sélectionner la ville à nettoyer", [f.replace("_data.csv","") for f in os.listdir(FOLDER_DATA)])
    if st.button("🔥 SUPPRIMER TOUTES LES DONNÉES DE CETTE VILLE"):
        os.remove(os.path.join(FOLDER_DATA, f"{v_clean}_data.csv"))
        st.success("Fichier supprimé. La ville est remise à zéro.")
        st.rerun()