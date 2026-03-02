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

# --- 1. CONFIGURATION ET RÉFÉRENTIEL ---
st.set_page_config(page_title="SODEXAM - Système de Gestion Pluviométrique", layout="wide", page_icon="🌧️")

if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# Coordonnées des stations pour la spatialisation sur la carte
COORDS_STATIONS = {
    "Abidjan": [5.3364, -4.0267], "Bouaké": [7.6939, -5.0303], "Yamoussoukro": [6.8276, -5.2767],
    "Korhogo": [9.4580, -5.6290], "San-Pédro": [4.7485, -6.6363], "Man": [7.4125, -7.5538],
    "Odienné": [9.5051, -7.5643], "Daloa": [6.8774, -6.4502], "Bondoukou": [8.0402, -2.8001],
    "Ferkessédougou": [9.5928, -5.1983], "Sassandra": [4.9538, -6.0853], "Tabou": [4.4230, -7.3528]
}

# --- 2. FONCTIONS DE GESTION DES DONNÉES ---
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
    if not df.empty:
        df['Date_Heure'] = pd.to_datetime(df['Date_Heure'], errors='coerce')
    return df

def envoyer_email_archive(destinataire, fichier_zip, periode_str):
    # --- CONFIGURATION GMAIL (À REMPLIR) ---
    expediteur = "votre_mail@gmail.com" 
    mot_de_passe_app = "votre_code_16_lettres" 
    
    msg = MIMEMultipart()
    msg['From'] = expediteur; msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - RAPPORT PLUVIOMÉTRIQUE : {periode_str}"
    msg.attach(MIMEText(f"Archive des données générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", 'plain'))
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
        st.error(f"Erreur d'envoi : {e}"); return False

# --- 3. SYSTÈME D'AUTHENTIFICATION ---
if 'connecte' not in st.session_state: st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM - PORTAIL DE GESTION</h1>", unsafe_allow_html=True)
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
    # --- BARRE LATÉRALE DE NAVIGATION ---
    st.sidebar.title("SODEXAM")
    st.sidebar.info(f"📍 Station : **{st.session_state.user_ville}**\n\n👤 Rôle : **{st.session_state.user_role.upper()}**")
    
    menu = ["🌍 Carte Interactive", "📝 Saisie Relevé", "📚 Historique & Corrections", "📈 Analyses Graphiques"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin (Export/Email)")
        menu.append("⚙️ Gestion des Comptes")
    
    choix = st.sidebar.radio("Navigation Menu", menu)
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False; st.rerun()

    # --- 4. 🌍 CARTE INTERACTIVE (SPATIALISATION) ---
    if choix == "🌍 Carte Interactive":
        st.header("🌍 État Pluviométrique National")
        df_total = charger_toutes_donnees()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        
        for ville, coords in COORDS_STATIONS.items():
            color = "gray"
            popup_text = f"<b>Station: {ville}</b><br>Aucune donnée enregistrée."
            
            if not df_total.empty:
                dv = df_total[df_total['Ville'] == ville]
                if not dv.empty:
                    last = dv.sort_values('Date_Heure').iloc[-1]
                    pluie = last['Pluie (mm)']
                    color = "blue" if pluie > 0 else "green"
                    popup_text = f"<b>{ville}</b><br>Pluie: {pluie} mm<br>Phénomènes: {last.get('Phenomenes', 'Néant')}<br>Date: {last['Date_Heure']}"
            
            folium.Marker(location=coords, popup=folium.Popup(popup_text, max_width=300), 
                          tooltip=ville, icon=folium.Icon(color=color, icon='tint')).add_to(m)
        st_folium(m, width="100%", height=550)

    # --- 5. 📊 DASHBOARD ADMIN (ENVOI EMAIL) ---
    elif choix == "📊 Dashboard Admin (Export/Email)":
        st.header("📊 Supervision et Exportation")
        df_total = charger_toutes_donnees()
        if not df_total.empty:
            dest_mail = st.text_input("Email du destinataire", "direction@sodexam.ci")
            if st.button("📤 Générer ZIP et Envoyer par Mail", type="primary"):
                nom_zip = f"SODEXAM_RAPPORT_{datetime.now().strftime('%Y%m%d')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in os.listdir("Donnees_Villes"): z.write(os.path.join("Donnees_Villes", f), f)
                if envoyer_email_archive(dest_mail, nom_zip, "Toutes Stations"):
                    st.success(f"Archive envoyée avec succès à {dest_mail} !"); os.remove(nom_zip)
        else: st.info("Aucune donnée disponible pour l'envoi.")

    # --- 6. 📝 SAISIE RELEVÉ (AVEC PHÉNOMÈNES) ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"📝 Saisie Station : {st.session_state.user_ville}")
        with st.form("form_saisie"):
            col1, col2 = st.columns(2)
            with col1:
                d = st.date_input("Date")
                h = st.selectbox("Heure Synoptique", ["08:00", "18:00", "Spécial"])
            with col2:
                p = st.number_input("Pluie (mm)", min_value=0.0, step=0.1)
                phenos = st.multiselect("Phénomènes", ["Orage", "Vent Fort", "Brouillard", "Brume", "Éclairs", "Grêle"])
            
            obs = st.text_area("Observations")
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                df_new = pd.DataFrame({
                    "Date_Heure": [f"{d} {h}"], 
                    "Pluie (mm)": [p], 
                    "Phenomenes": [", ".join(phenos) if phenos else "Néant"],
                    "Observations": [obs]
                })
                df_new.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
                st.success("✅ Donnée enregistrée avec succès !")

    # --- 7. 📚 HISTORIQUE (MODIFIER / SUPPRIMER / RÉINITIALISER - ADMIN SEUL) ---
    elif choix == "📚 Historique & Corrections":
        st.header("📚 Consultation et Gestion des Historiques")
        
        # Sélection de la station (Admin choisit, Agent subit sa station)
        if st.session_state.user_role == "admin":
            v_list = [f.replace(".csv","") for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
            v_sel = st.selectbox("Sélectionner une station à gérer", v_list)
        else:
            v_sel = st.session_state.user_ville
            st.info(f"Visualisation des relevés de {v_sel}")

        path = f"Donnees_Villes/{v_sel}.csv"
        if os.path.exists(path):
            df_h = pd.read_csv(path)
            
            if st.session_state.user_role == "admin":
                st.subheader("🛠️ Espace de Correction (ADMIN)")
                st.info("Vous pouvez modifier les valeurs directement dans le tableau ci-dessous.")
                
                # --- OPTION MODIFIER ---
                df_edite = st.data_editor(df_h, num_rows="dynamic", key="editor_admin")
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Sauvegarder les modifications"):
                    df_edite.to_csv(path, index=False)
                    st.success("Les corrections ont été appliquées !")
                    st.rerun()
                
                # --- OPTION RÉINITIALISER ---
                if c2.button("⚠️ RÉINITIALISER LA STATION (Vider)", type="secondary"):
                    os.remove(path)
                    st.warning(f"La station {v_sel} a été réinitialisée (toutes les données sont supprimées).")
                    st.rerun()
            else:
                # Vue simple en lecture seule pour les agents
                st.dataframe(df_h, use_container_width=True)
        else: st.info("Aucun historique pour cette station.")

    # --- 8. ⚙️ GESTION COMPTES (SUPPRIMER COMPTE - ADMIN SEUL) ---
    elif choix == "⚙️ Gestion des Comptes":
        st.header("⚙️ Administration des Utilisateurs")
        u_df = charger_utilisateurs()
        
        # Affichage avec option suppression
        for i, r in u_df.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"👤 **{r['identifiant']}**")
            col2.write(f"📍 Station: {r['ville']}")
            if r['identifiant'] != "admin" and col3.button("🗑️ Supprimer", key=f"del_{i}"):
                u_df.drop(i).to_csv("utilisateurs.csv", index=False)
                st.rerun()
        
        with st.form("add_user"):
            st.write("➕ Ajouter ou réinitialiser un compte Agent")
            ni, np, nv = st.text_input("Identifiant"), st.text_input("Nouveau Pass"), st.text_input("Ville")
            if st.form_submit_button("Valider"):
                if ni in u_df['identifiant'].values:
                    u_df.loc[u_df['identifiant'] == ni, ['mot_de_passe', 'ville']] = [np, nv]
                else:
                    u_df = pd.concat([u_df, pd.DataFrame({"identifiant":[ni],"mot_de_passe":[np],"ville":[nv],"role":["agent"]})])
                u_df.to_csv("utilisateurs.csv", index=False); st.success("Compte mis à jour !"); st.rerun()