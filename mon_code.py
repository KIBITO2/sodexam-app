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

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="SODEXAM - Gestion Intégrée", layout="wide", page_icon="🌧️")

# RÉFÉRENTIEL DES STATIONS (X, Y pour Surfer 13)
COORDS_STATIONS = {
    "Abidjan": [5.3364, -4.0267], "Bouaké": [7.6939, -5.0303], "Yamoussoukro": [6.8276, -5.2767],
    "Korhogo": [9.4580, -5.6290], "San-Pédro": [4.7485, -6.6363], "Man": [7.4125, -7.5538],
    "Odienné": [9.5051, -7.5643], "Daloa": [6.8774, -6.4502], "Bondoukou": [8.0402, -2.8001],
    "Ferkessédougou": [9.5928, -5.1983], "Sassandra": [4.9538, -6.0853], "Tabou": [4.4230, -7.3528]
}

# --- 2. CONNEXION GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def charger_releves():
    # Lit le PREMIER onglet (index 0)
    return conn.read(worksheet=0)

def charger_utilisateurs():
    # Lit le DEUXIÈME onglet (index 1)
    return conn.read(worksheet=1)

# --- 3. FONCTION EMAIL (SÉCURISÉE) ---
def envoyer_email_archive(destinataire, fichier_zip):
    try:
        expediteur = st.secrets["lateseraphinkone@gmail.com"]
        mot_de_passe_app = st.secrets["wdgu cdog ddjp gxlw"]
        
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

# --- 4. LOGIQUE D'AUTHENTIFICATION ---
if 'connecte' not in st.session_state: st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center;'>🔐 CONNEXION SODEXAM</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant Agent")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            try:
                users = charger_utilisateurs()
                # Vérification (Colonnes: username, password, ville, role)
                user_match = users[(users['username'].astype(str) == u) & (users['password'].astype(str) == p)]
                if not user_match.empty:
                    st.session_state.update({
                        "connecte": True, 
                        "user_ville": user_match.iloc[0]['ville'], 
                        "user_role": user_match.iloc[0]['role']
                    })
                    st.rerun()
                else: st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error("⚠️ Impossible de lire la base utilisateur. Vérifiez que l'onglet des accès est en DEUXIÈME position dans Google Sheets.")
else:
    # --- BARRE LATÉRALE ---
    st.sidebar.title("SODEXAM")
    st.sidebar.write(f"📍 **{st.session_state.user_ville}**")
    st.sidebar.write(f"👤 Rôle : {st.session_state.user_role.upper()}")
    
    menu = ["🌍 Carte Interactive", "📝 Saisie Relevé", "📚 Historique", "📈 Analyses"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin")
    
    choix = st.sidebar.radio("Navigation", menu)
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False; st.rerun()

    # --- 🌍 CARTE ---
    if choix == "🌍 Carte Interactive":
        st.header("🌍 Réseau Pluviométrique")
        df_total = charger_releves()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        for v, coords in COORDS_STATIONS.items():
            color = "gray"
            if not df_total.empty:
                last = df_total[df_total['Station'] == v]
                if not last.empty:
                    color = "blue" if last.iloc[-1]['Pluie (mm)'] > 0 else "green"
            folium.Marker(location=coords, popup=v, icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=500)

    # --- 📝 SAISIE ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"📝 Nouveau Relevé : {st.session_state.user_ville}")
        df_actuel = charger_releves()
        with st.form("form_saisie"):
            d = st.date_input("Date")
            p = st.number_input("Pluie (mm)", min_value=0.0, step=0.1)
            obs = st.text_area("Observations")
            if st.form_submit_button("💾 Enregistrer"):
                lat_lon = COORDS_STATIONS.get(st.session_state.user_ville, [0.0, 0.0])
                df_new = pd.DataFrame([{
                    "Date_Heure": str(d), "Station": st.session_state.user_ville,
                    "Pluie (mm)": p, "Obs": obs, "Lat": lat_lon[0], "Lon": lat_lon[1]
                }])
                df_final = pd.concat([df_actuel, df_new], ignore_index=True)
                conn.update(worksheet=0, data=df_final)
                st.success("Donnée envoyée au Cloud !")

    # --- 📊 ADMIN ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Export & Sécurité")
        df_total = charger_releves()
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗺️ Export SURFER 13")
            df_surfer = df_total[['Lon', 'Lat', 'Pluie (mm)']]
            st.download_button("📥 Télécharger CSV (X,Y,Z)", df_surfer.to_csv(index=False), "data_surfer.csv")
            
        with c2:
            st.subheader("📬 Archive Email")
            dest = st.text_input("Destinataire", "direction@sodexam.ci")
            if st.button("📤 Envoyer Archive ZIP"):
                df_total.to_csv("donnees.csv", index=False)
                with zipfile.ZipFile("sodexam.zip", 'w') as z: z.write("donnees.csv")
                if envoyer_email_archive(dest, "sodexam.zip"): st.success("Email envoyé !")
                os.remove("donnees.csv"); os.remove("sodexam.zip")

    # --- 📚 HISTORIQUE ---
    elif choix == "📚 Historique":
        df_h = charger_releves()
        if st.session_state.user_role == "admin":
            st.subheader("Modifier la base globale")
            df_edite = st.data_editor(df_h, num_rows="dynamic")
            if st.button("💾 Sauvegarder"):
                conn.update(worksheet=0, data=df_edite); st.rerun()
        else:
            st.dataframe(df_h[df_h['Station'] == st.session_state.user_ville])

    # --- 📈 ANALYSES ---
    elif choix == "📈 Analyses":
        df_t = charger_releves()
        if not df_t.empty:
            st.plotly_chart(px.line(df_t, x='Date_Heure', y='Pluie (mm)', color='Station'))
