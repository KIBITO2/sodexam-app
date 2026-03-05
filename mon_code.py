import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
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

# Création des dossiers si inexistants
if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# RÉFÉRENTIEL DES STATIONS (Spatialisation)
COORDS_STATIONS = {
    "Abidjan": [5.3364, -4.0267], "Bouaké": [7.6939, -5.0303], "Yamoussoukro": [6.8276, -5.2767],
    "Korhogo": [9.4580, -5.6290], "San-Pédro": [4.7485, -6.6363], "Man": [7.4125, -7.5538],
    "Odienné": [9.5051, -7.5643], "Daloa": [6.8774, -6.4502], "Bondoukou": [8.0402, -2.8001],
    "Ferkessédougou": [9.5928, -5.1983], "Sassandra": [4.9538, -6.0853], "Tabou": [4.4230, -7.3528]
}

# --- 2. FONCTIONS DE GESTION ---
def charger_utilisateurs():
    if os.path.exists("utilisateurs.csv"): return pd.read_csv("utilisateurs.csv")
    df = pd.DataFrame({"identifiant": ["admin"], "mot_de_passe": ["admin123"], "ville": ["Abidjan"], "role": ["admin"]})
    df.to_csv("utilisateurs.csv", index=False)
    return df

def charger_toutes_donnees():
    fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
    if not fichiers: return pd.DataFrame()
    all_dfs = []
    for f in fichiers:
        temp_df = pd.read_csv(os.path.join("Donnees_Villes", f))
        temp_df['Ville'] = f.replace(".csv","")
        all_dfs.append(temp_df)
    df = pd.concat(all_dfs)
    if not df.empty:
        df['Date_Heure'] = pd.to_datetime(df['Date_Heure'], errors='coerce')
        df = df.dropna(subset=['Date_Heure'])
        df = df.sort_values('Date_Heure')
    return df

def envoyer_email_archive(destinataire, fichier_zip, periode_str):
    # --- CONFIGURATION GMAIL (A REMPLIR) ---
    expediteur = "votre_mail@gmail.com" 
    mot_de_passe_app = "votre_code_16_lettres" 
    
    msg = MIMEMultipart()
    msg['From'] = expediteur; msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - ARCHIVE : {periode_str}"
    msg.attach(MIMEText(f"Rapport généré le {datetime.now().strftime('%d/%m/%Y')}", 'plain'))
    try:
        with open(fichier_zip, "rb") as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read()); encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={fichier_zip}")
            msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(expediteur, mot_de_passe_app); server.send_message(msg); server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur Mail: {e}"); return False

# --- 3. GESTION DU LOGO ---
def afficher_logo():
    logo_possible = ["logo.png", "logo.jpg", "logo.jpeg", "LOGO.PNG", "LOGO.JPG"]
    trouve = False
    for img in logo_possible:
        if os.path.exists(img):
            st.sidebar.image(img, use_container_width=True)
            trouve = True
            break
    if not trouve:
        st.sidebar.markdown("<h2 style='text-align: center; color: #004a99;'>SODEXAM</h2>", unsafe_allow_html=True)

# --- 4. AUTHENTIFICATION ---
if 'connecte' not in st.session_state: st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center;'>🔐 CONNEXION SODEXAM</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            users = charger_utilisateurs()
            user = users[(users['identifiant'].astype(str) == u) & (users['mot_de_passe'].astype(str) == p)]
            if not user.empty:
                st.session_state.update({"connecte": True, "user_ville": user.iloc[0]['ville'], "user_role": user.iloc[0]['role']})
                st.rerun()
            else: st.error("Accès refusé.")
else:
    # --- BARRE LATÉRALE ---
    afficher_logo()
    st.sidebar.divider()
    st.sidebar.write(f"📍 Station : **{st.session_state.user_ville}**")
    st.sidebar.write(f"👤 Rôle : **{st.session_state.user_role.upper()}**")
    
    menu = ["🌍 Carte Interactive", "📝 Saisie Relevé", "📚 Historique & Corrections", "📈 Analyses Graphiques"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin (Email)")
        menu.append("⚙️ Gestion des Comptes")
    
    choix = st.sidebar.radio("Navigation", menu)
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False; st.rerun()

    # --- 🌍 CARTE INTERACTIVE ---
    if choix == "🌍 Carte Interactive":
        st.header("🌍 État Pluviométrique National")
        df_total = charger_toutes_donnees()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        for v, coords in COORDS_STATIONS.items():
            color, info = "gray", f"Station: {v}<br>Aucune donnée."
            if not df_total.empty:
                dv = df_total[df_total['Ville'] == v]
                if not dv.empty:
                    last = dv.sort_values('Date_Heure').iloc[-1]
                    color = "blue" if last['Pluie (mm)'] > 0 else "green"
                    info = f"<b>{v}</b><br>Dernier: {last['Pluie (mm)']} mm<br>Phénomène: {last.get('Phenomenes', 'RAS')}"
            folium.Marker(location=coords, popup=folium.Popup(info, max_width=300), icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=550)

    # --- 📝 SAISIE RELEVÉ (AVEC PHÉNOMÈNES) ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"📝 Saisie : {st.session_state.user_ville}")
        with st.form("form_saisie"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Date")
            h = c1.selectbox("Heure", ["08:00", "18:00", "Spécial"])
            p = c2.number_input("Pluie (mm)", min_value=0.0, step=0.1)
            ph = c2.multiselect("Phénomènes", ["Orage", "Vent Fort", "Brume", "Brouillard", "Rosée"])
            obs = st.text_area("Observations")
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                df_new = pd.DataFrame({"Date_Heure":[f"{d} {h}"], "Pluie (mm)":[p], "Phenomenes":[", ".join(ph)], "Obs":[obs]})
                df_new.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
                st.success("Donnée enregistrée !")

    # --- 📚 HISTORIQUE & ADMIN (SUPPRIMER / MODIFIER / RÉINITIALISER) ---
    elif choix == "📚 Historique & Corrections":
        st.header("📚 Gestion de l'Historique")
        v_sel = st.selectbox("Station", [f.replace(".csv","") for f in os.listdir("Donnees_Villes")]) if st.session_state.user_role == "admin" else st.session_state.user_ville
        path = f"Donnees_Villes/{v_sel}.csv"
        if os.path.exists(path):
            df_h = pd.read_csv(path)
            if st.session_state.user_role == "admin":
                st.subheader("🛠️ Zone Admin : Correction & Suppression")
                df_edite = st.data_editor(df_h, num_rows="dynamic")
                c1, c2 = st.columns(2)
                if c1.button("💾 Sauvegarder Corrections"): df_edite.to_csv(path, index=False); st.success("Mis à jour !"); st.rerun()
                if c2.button("🗑️ Vider la Station (Réinitialiser)", type="secondary"): os.remove(path); st.warning("Données effacées."); st.rerun()
            else: st.dataframe(df_h, use_container_width=True)
        else: st.info("Aucun historique trouvé.")

    # --- 📊 DASHBOARD ADMIN (EMAIL) ---
    elif choix == "📊 Dashboard Admin (Email)":
        st.header("📊 Exportation des Données")
        email = st.text_input("Destinataire", "direction@sodexam.ci")
        if st.button("📤 Envoyer Archive ZIP"):
            nom_zip = f"SODEXAM_{datetime.now().strftime('%Y%m%d')}.zip"
            with zipfile.ZipFile(nom_zip, 'w') as z:
                for f in os.listdir("Donnees_Villes"): z.write(os.path.join("Donnees_Villes", f), f)
            if envoyer_email_archive(email, nom_zip, "Global"): st.success("Email envoyé ! \n(Vérifiez vos 16 lettres Gmail ligne 51)"); os.remove(nom_zip)

    # --- ⚙️ GESTION COMPTES ---
    elif choix == "⚙️ Gestion des Comptes":
        st.header("⚙️ Comptes Utilisateurs")
        u_df = charger_utilisateurs()
        for i, r in u_df.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"👤 {r['identifiant']} ({r['ville']})")
            if r['identifiant'] != "admin" and col3.button("🗑️ Supprimer", key=f"u_{i}"):
                u_df.drop(i).to_csv("utilisateurs.csv", index=False); st.rerun()
        with st.form("add"):
            st.write("➕ Ajouter / Réinitialiser Pass")
            ni, np, nv = st.text_input("ID"), st.text_input("Pass"), st.text_input("Ville")
            if st.form_submit_button("Enregistrer"):
                u_df = pd.concat([u_df[u_df['identifiant'] != ni], pd.DataFrame({"identifiant":[ni],"mot_de_passe":[np],"ville":[nv],"role":["agent"]})])
                u_df.to_csv("utilisateurs.csv", index=False); st.success("Compte mis à jour !"); st.rerun()

    # --- 📈 ANALYSES GRAPHIQUES ---
    elif choix == "📈 Analyses Graphiques":
        st.header("📈 Graphiques des Précipitations")
        df_t = charger_toutes_donnees()
        if not df_t.empty:
            v_plot = st.multiselect("Villes à comparer", sorted(df_t['Ville'].unique()), default=df_t['Ville'].unique()[:1])
            if v_plot:
                df_p = df_t[df_t['Ville'].isin(v_plot)]
                st.plotly_chart(px.line(df_p, x='Date_Heure', y='Pluie (mm)', color='Ville', markers=True, title="Évolution des Pluies"), use_container_width=True)
                
                st.plotly_chart(px.bar(df_p.groupby('Ville')['Pluie (mm)'].sum().reset_index(), x='Ville', y='Pluie (mm)', color='Ville', title="Cumul Total"), use_container_width=True)
                
            else: st.warning("Sélectionnez une ville.")
        else: st.info("Aucune donnée pour les graphiques.")