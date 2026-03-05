import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import os
import zipfile
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SODEXAM - Gestion Intégrée", layout="wide", page_icon="🌧️")

# --- 2. CONNEXION GOOGLE SHEETS ---
# On ajoute ttl=0 pour forcer Streamlit à lire les données réelles sans attendre
conn = st.connection("gsheets", type=GSheetsConnection)

def charger_releves():
    # Lit le premier onglet (index 0)
    return conn.read(worksheet=0, ttl=0)

def charger_utilisateurs():
    # Lit le deuxième onglet (index 1)
    return conn.read(worksheet=1, ttl=0)

# --- 3. FONCTION EMAIL ---
def envoyer_email_archive(destinataire, fichier_zip):
    try:
        expediteur = st.secrets["EMAIL_USER"]
        mot_de_passe_app = st.secrets["EMAIL_PASS"]
        msg = MIMEMultipart()
        msg['From'] = expediteur
        msg['To'] = destinataire
        msg['Subject'] = f"SODEXAM ARCHIVE - {datetime.now().strftime('%d/%m/%Y')}"
        msg.attach(MIMEText("Ci-joint l'archive des données pluviométriques.", 'plain'))
        with open(fichier_zip, "rb") as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={fichier_zip}")
            msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(expediteur, mot_de_passe_app)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur Mail : {e}")
        return False

# RÉFÉRENTIEL DES STATIONS
COORDS_STATIONS = {
    "Abidjan": [5.3364, -4.0267], "Bouaké": [7.6939, -5.0303], "Yamoussoukro": [6.8276, -5.2767],
    "Korhogo": [9.4580, -5.6290], "San-Pédro": [4.7485, -6.6363], "Man": [7.4125, -7.5538],
    "Odienné": [9.5051, -7.5643], "Daloa": [6.8774, -6.4502], "Bondoukou": [8.0402, -2.8001],
    "Ferkessédougou": [9.5928, -5.1983], "Sassandra": [4.9538, -6.0853], "Tabou": [4.4230, -7.3528]
}

# --- 4. AUTHENTIFICATION ---
if 'connecte' not in st.session_state: st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center;'>🔐 CONNEXION SODEXAM</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant Agent")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            try:
                # Tentative de lecture forcée
                users = charger_utilisateurs()
                # On nettoie les espaces éventuels dans les noms de colonnes
                users.columns = users.columns.str.strip()
                
                user_match = users[(users['username'].astype(str) == str(u)) & (users['password'].astype(str) == str(p))]
                
                if not user_match.empty:
                    st.session_state.update({
                        "connecte": True, 
                        "user_ville": user_match.iloc[0]['ville'], 
                        "user_role": user_match.iloc[0]['role']
                    })
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error("⚠️ Erreur de lecture du tableau.")
                st.write("Détail technique : ", e)
else:
    # --- INTERFACE PRINCIPALE ---
    st.sidebar.title("SODEXAM")
    st.sidebar.write(f"📍 **{st.session_state.user_ville}**")
    
    menu = ["🌍 Carte Interactive", "📝 Saisie Relevé", "📚 Historique", "📈 Analyses"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin")
    
    choix = st.sidebar.radio("Navigation", menu)
    
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 🌍 CARTE ---
    if choix == "🌍 Carte Interactive":
        st.header("🌍 Réseau Pluviométrique")
        df_total = charger_releves()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        for v, coords in COORDS_STATIONS.items():
            folium.Marker(location=coords, popup=v).add_to(m)
        st_folium(m, width="100%", height=500)

    # --- 📝 SAISIE ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"📝 Nouveau Relevé : {st.session_state.user_ville}")
        if st.form("form_saisie"):
            d = st.date_input("Date")
            p = st.number_input("Pluie (mm)", min_value=0.0)
            if st.form_submit_button("Enregistrer"):
                df_actuel = charger_releves()
                lat_lon = COORDS_STATIONS.get(st.session_state.user_ville, [0.0, 0.0])
                df_new = pd.DataFrame([{"Date_Heure": str(d), "Station": st.session_state.user_ville, "Pluie (mm)": p, "Lat": lat_lon[0], "Lon": lat_lon[1]}])
                df_final = pd.concat([df_actuel, df_new], ignore_index=True)
                conn.update(worksheet=0, data=df_final)
                st.success("Donnée enregistrée !")

    # --- 📊 ADMIN ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Export & Sécurité")
        df_total = charger_releves()
        st.subheader("🗺️ Export SURFER 13")
        df_surfer = df_total[['Lon', 'Lat', 'Pluie (mm)']]
        st.download_button("📥 Télécharger CSV (X,Y,Z)", df_surfer.to_csv(index=False), "data_surfer.csv")
