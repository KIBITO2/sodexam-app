import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os
import zipfile
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. CONFIGURATION SYSTÈME ---
st.set_page_config(page_title="SODEXAM - Système Expert", layout="wide", page_icon="🌧️")

if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

COORDS_STATIONS = {
    "Abidjan": [5.3364, -4.0267], "Bouaké": [7.6939, -5.0303], "Yamoussoukro": [6.8276, -5.2767],
    "Korhogo": [9.4580, -5.6290], "San-Pédro": [4.7485, -6.6363], "Man": [7.4125, -7.5538]
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
    all_dfs = [pd.read_csv(os.path.join("Donnees_Villes", f)).assign(Ville=f.replace(".csv","")) for f in fichiers]
    df = pd.concat(all_dfs)
    df['Date_Heure'] = pd.to_datetime(df['Date_Heure'])
    return df

def envoyer_email_archive(destinataire, fichier_zip, periode_str):
    # --- CONFIGURATION GMAIL (À REMPLIR) ---
    expediteur = "lateseraphinkone@gmail.com" 
    mot_de_passe_app = "wdgu cdog ddjp gxlw" 
    
    msg = MIMEMultipart()
    msg['From'] = expediteur; msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - ARCHIVE PLUVIO : {periode_str}"
    msg.attach(MIMEText(f"Veuillez trouver ci-joint l'archive des relevés pour : {periode_str}", 'plain'))
    
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
        st.error(f"Erreur d'envoi Mail : {e}"); return False

# --- 3. AUTHENTIFICATION ---
if 'connecte' not in st.session_state: st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM - CONNEXION</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant").strip()
        p = st.text_input("Mot de passe", type="password").strip()
        if st.button("Se connecter", use_container_width=True):
            users = charger_utilisateurs()
            user = users[(users['identifiant'].astype(str) == u) & (users['mot_de_passe'].astype(str) == p)]
            if not user.empty:
                st.session_state.update({"connecte": True, "user_ville": user.iloc[0]['ville'], "user_role": user.iloc[0]['role']})
                st.rerun()
            else: st.error("Identifiants incorrects.")
else:
    # --- BARRE LATÉRALE ---
    st.sidebar.title("SODEXAM")
    st.sidebar.write(f"🟢 **{st.session_state.user_ville}** ({st.session_state.user_role})")
    
    menu = ["🌍 Carte du Réseau", "📝 Saisie Relevé", "📚 Historique", "📈 Analyses & Graphiques"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin")
        menu.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Navigation", menu)
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False; st.rerun()

    # --- 🌍 CARTE ---
    if choix == "🌍 Carte du Réseau":
        st.header("🌍 Carte des Stations")
        df_total = charger_toutes_donnees()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        for v, coords in COORDS_STATIONS.items():
            color = "gray"
            if not df_total.empty:
                dv = df_total[df_total['Ville'] == v]
                if not dv.empty:
                    last = dv.sort_values('Date_Heure').iloc[-1]
                    color = "blue" if last['Pluie (mm)'] > 0 else "green"
            folium.Marker(location=coords, popup=v, icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=500)

    # --- 📊 DASHBOARD ADMIN (L'OPTION ENVOI EMAIL EST ICI) ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Supervision & Envoi des Rapports")
        df_total = charger_toutes_donnees()
        if not df_total.empty:
            c1, c2 = st.columns(2)
            an_sel = c1.selectbox("Filtrer par Année", ["Toutes"] + list(df_total['Date_Heure'].dt.year.unique()))
            mo_sel = c2.selectbox("Filtrer par Mois", ["Tous", "Janv", "Fév", "Mars", "Avril", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"])
            
            st.divider()
            email_dest = st.text_input("Email du destinataire", "direction@sodexam.ci")
            if st.button("📤 Générer Archive et Envoyer par Mail", type="primary"):
                nom_zip = f"Archive_SODEXAM_{datetime.now().strftime('%Y%m%d')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in os.listdir("Donnees_Villes"): z.write(os.path.join("Donnees_Villes", f), f)
                if envoyer_email_archive(email_dest, nom_zip, f"{mo_sel} {an_sel}"):
                    st.success(f"Archive envoyée avec succès à {email_dest}")
                    os.remove(nom_zip)
        else: st.info("Aucune donnée disponible pour l'envoi.")

    # --- 📝 SAISIE RELEVÉ (AGENTS & ADMIN) ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"📝 Saisie Station : {st.session_state.user_ville}")
        with st.form("saisie"):
            d = st.date_input("Date"); h = st.selectbox("Heure", ["08:00", "18:00"])
            p = st.number_input("Pluie (mm)", min_value=0.0)
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                pd.DataFrame({"Date_Heure":[f"{d} {h}"], "Pluie (mm)":[p]}).to_csv(path, mode='a', header=not os.path.exists(path), index=False)
                st.success("Donnée enregistrée.")

    # --- 📚 HISTORIQUE (CORRECTION & SUPPRESSION ADMIN SEULEMENT) ---
    elif choix == "📚 Historique":
        st.header("📚 Gestion de l'Historique")
        if st.session_state.user_role == "admin":
            villes = [f.replace(".csv","") for f in os.listdir("Donnees_Villes")]
            v_sel = st.selectbox("Station à gérer", villes)
        else: v_sel = st.session_state.user_ville
        
        path = f"Donnees_Villes/{v_sel}.csv"
        if os.path.exists(path):
            df_h = pd.read_csv(path)
            if st.session_state.user_role == "admin":
                st.subheader("🛠️ Espace de Correction (ADMIN)")
                # Éditeur dynamique pour corriger ou supprimer des lignes
                df_corrige = st.data_editor(df_h, num_rows="dynamic", key="editor")
                if st.button("💾 Sauvegarder les corrections"):
                    df_corrige.to_csv(path, index=False); st.success("Fichier mis à jour !"); st.rerun()
                if st.button("⚠️ Tout Effacer pour cette ville"):
                    os.remove(path); st.warning("Données supprimées."); st.rerun()
            else:
                st.dataframe(df_h, use_container_width=True)
        else: st.info("Aucune donnée.")

    # --- 📈 ANALYSES & GRAPHIQUES ---
    elif choix == "📈 Analyses & Graphiques":
        st.header("📈 Visualisation des Données")
        df_total = charger_toutes_donnees()
        if not df_total.empty:
            v_plot = st.multiselect("Villes", df_total['Ville'].unique(), default=df_total['Ville'].unique()[:1])
            df_filt = df_total[df_total['Ville'].isin(v_plot)]
            st.plotly_chart(px.line(df_filt, x='Date_Heure', y='Pluie (mm)', color='Ville'), use_container_width=True)
            st.plotly_chart(px.bar(df_filt.groupby('Ville')['Pluie (mm)'].sum().reset_index(), x='Ville', y='Pluie (mm)'), use_container_width=True)

    # --- ⚙️ GESTION COMPTES (SUPPRESSION & RÉINITIALISATION ADMIN) ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("⚙️ Administration des Utilisateurs")
        u_df = charger_utilisateurs()
        for i, r in u_df.iterrows():
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"👤 {r['identifiant']} ({r['ville']})")
            if r['identifiant'] != "admin" and c3.button("🗑️", key=f"u_{i}"):
                u_df.drop(i).to_csv("utilisateurs.csv", index=False); st.rerun()
        with st.form("u_add"):
            st.write("➕ Ajouter / Modifier (Réinitialiser)")
            ni, np, nv = st.text_input("Identifiant"), st.text_input("Nouveau Pass"), st.text_input("Ville")
            if st.form_submit_button("Sauvegarder"):
                if ni in u_df['identifiant'].values:
                    u_df.loc[u_df['identifiant'] == ni, ['mot_de_passe', 'ville']] = [np, nv]
                else:
                    u_df = pd.concat([u_df, pd.DataFrame({"identifiant":[ni],"mot_de_passe":[np],"ville":[nv],"role":["agent"]})])
                u_df.to_csv("utilisateurs.csv", index=False); st.success("Compte mis à jour !"); st.rerun()