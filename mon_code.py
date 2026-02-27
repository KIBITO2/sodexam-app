import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import zipfile
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SODEXAM - Gestion Pluviométrique", layout="wide", page_icon="🌧️")

# Création des dossiers de stockage
if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# --- FONCTIONS TECHNIQUES ---

def charger_utilisateurs():
    nom_f = "utilisateurs.csv"
    if os.path.exists(nom_f):
        try:
            df = pd.read_csv(nom_f, sep=None, engine='python')
            if 'identifiant' in df.columns: return df
        except: pass
    # Admin par défaut
    df_admin = pd.DataFrame({"identifiant": ["admin"], "mot_de_passe": ["admin123"], "ville": ["Abidjan"], "role": ["admin"]})
    df_admin.to_csv(nom_f, index=False)
    return df_admin

def charger_villes_coords():
    nom_f = "villes_ci.csv"
    if os.path.exists(nom_f):
        try:
            df = pd.read_csv(nom_f, sep=None, engine='python')
            if 'Ville' in df.columns: return df
        except: pass
    df_v = pd.DataFrame({"Ville": ["Abidjan"], "Lat": [5.309], "Lon": [-4.012]})
    df_v.to_csv(nom_f, index=False)
    return df_v

def envoyer_email_archive(destinataire, fichier_zip):
    # --- CONFIGURATION EMAIL ---
    expediteur = "lateseraphinkone@gmail.com" # À REMPLACER
    mot_de_passe = "wdgu cdog ddjp gxlw" # À REMPLACER
    
    msg = MIMEMultipart()
    msg['From'] = expediteur
    msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - Archive Hebdomadaire {datetime.now().strftime('%d/%m/%Y')}"
    
    corps = "Bonjour,\n\nVeuillez trouver ci-joint l'archive ZIP des relevés pluviométriques."
    msg.attach(MIMEText(corps, 'plain'))
    
    with open(fichier_zip, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {fichier_zip}")
        msg.attach(part)
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(expediteur, mot_de_passe)
    server.send_message(msg)
    server.quit()

# --- GESTION DE LA SESSION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False
    st.session_state.user_role = ""
    st.session_state.user_ville = ""
    st.session_state.save_success = False

# --- INTERFACE DE CONNEXION ---
if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter", use_container_width=True):
            users = charger_utilisateurs()
            user = users[(users['identifiant'].astype(str) == u) & (users['mot_de_passe'].astype(str) == p)]
            if not user.empty:
                st.session_state.connecte = True
                st.session_state.user_ville = user.iloc[0]['ville']
                st.session_state.user_role = user.iloc[0]['role']
                st.rerun()
            else: st.error("Identifiants incorrects.")
else:
    # --- SIDEBAR & LOGO ---
    st.sidebar.title("SODEXAM")
    
    # Affichage du logo
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png", use_container_width=True)
    else:
        st.sidebar.warning("Logo introuvable (logo.png)")

    options = ["Carte Nationale", "Saisie Relevé", "Historique"]
    if st.session_state.user_role == "admin":
        options.insert(1, "📊 Dashboard Admin")
        options.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Menu Principal", options)
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 1. CARTE NATIONALE ---
    if choix == "Carte Nationale":
        st.header("📍 Réseau Pluviométrique National")
        villes_df = charger_villes_coords()
        m = folium.Map(location=[7.5399, -5.5471], zoom_start=7)
        for _, v in villes_df.iterrows():
            path = f"Donnees_Villes/{v['Ville']}.csv"
            color, info = "blue", f"<b>{v['Ville']}</b><br>Aucun relevé"
            if os.path.exists(path):
                df_v = pd.read_csv(path)
                if not df_v.empty:
                    dernier = df_v.iloc[-1]
                    color = "green" if dernier['Pluie (mm)'] < 50 else "red"
                    info = f"<b>{v['Ville']}</b><br>Collecte: {dernier['Date_Heure']}<br>Pluie: {dernier['Pluie (mm)']} mm"
            folium.Marker([v['Lat'], v['Lon']], popup=folium.Popup(info, max_width=200), icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=550)

    # --- 2. DASHBOARD ADMIN (LECTURE + ARCHIVE + PURGE) ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Supervision & Lecture Nationale")
        fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
        
        if fichiers:
            # Consolidation pour lecture
            all_dfs = [pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers]
            df_national = pd.concat(all_dfs).sort_values(by="Date_Heure", ascending=False)
            
            st.subheader("👀 Lecture des relevés récents")
            filtre = st.multiselect("Filtrer par localité", options=df_national['Ville'].unique())
            df_vue = df_national if not filtre else df_national[df_national['Ville'].isin(filtre)]
            st.dataframe(df_vue, use_container_width=True, height=350)

            st.divider()
            st.subheader("📧 Maintenance Hebdomadaire (Lundi 12h00)")
            dest = st.text_input("Envoyer l'archive à :", "direction@sodexam.ci")
            c1, c2 = st.columns(2)
            
            if c1.button("📨 1. Envoyer ZIP par Mail", use_container_width=True, type="primary"):
                nom_zip = f"Sodexam_Archive_{datetime.now().strftime('%d-%m-%Y')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in fichiers: z.write(os.path.join("Donnees_Villes", f), f)
                try:
                    envoyer_email_archive(dest, nom_zip)
                    st.session_state.save_success = True
                    st.success("Mail envoyé avec succès !")
                except Exception as e: st.error(f"Erreur d'envoi: {e}")

            if c2.button("🗑️ 2. Purger les données", use_container_width=True, disabled=not st.session_state.save_success):
                for f in fichiers: os.remove(os.path.join("Donnees_Villes", f))
                st.session_state.save_success = False
                st.success("Données purgées. Nouveau cycle démarré.")
                st.rerun()
        else: st.info("Aucune donnée collectée actuellement.")

    # --- 3. SAISIE RELEVÉ ---
    elif choix == "Saisie Relevé":
        st.header(f"Saisie : {st.session_state.user_ville}")
        with st.form("saisie"):
            col1, col2 = st.columns(2)
            d = col1.date_input("Date")
            h = col2.time_input("Heure précise")
            p = st.number_input("Pluviométrie (mm)", min_value=0.0)
            o = st.text_area("Observations")
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                timestamp = f"{d} {h.strftime('%H:%M')}"
                new_d = pd.DataFrame({"Date_Heure": [timestamp], "Pluie (mm)": [p], "Observations": [o]})
                if os.path.exists(path): new_d.to_csv(path, mode='a', header=False, index=False)
                else: new_d.to_csv(path, index=False)
                st.success("Donnée enregistrée !")

    # --- 4. HISTORIQUE (ADAPTATIF ADMIN / AGENT) ---
    elif choix == "Historique":
        if st.session_state.user_role == "admin":
            st.header("📚 Historique Global du Réseau")
            fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
            if fichiers:
                all_data = pd.concat([pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers])
                st.dataframe(all_data.sort_values(by="Date_Heure", ascending=False), use_container_width=True)
                st.download_button("📥 Télécharger Historique Global (CSV)", all_data.to_csv(index=False).encode('utf-8'), "historique_global.csv")
            else: st.info("Aucun relevé disponible.")
        else:
            st.header(f"Historique de {st.session_state.user_ville}")
            path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                df.insert(0, "Sélection", False)
                edited = st.data_editor(df, hide_index=True, use_container_width=True)
                if st.button("❌ Supprimer sélection"):
                    df_f = edited[edited["Sélection"] == False].drop(columns=["Sélection"])
                    df_f.to_csv(path, index=False)
                    st.rerun()
            else: st.info("Aucun historique.")

    # --- 5. GESTION COMPTES ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("Gestion des Agents et Stations")
        u_df = charger_utilisateurs()
        
        # Affichage de la liste existante
        st.subheader("👥 Comptes déjà créés")
        st.dataframe(u_df[['identifiant', 'ville', 'role']], use_container_width=True)
        
        st.divider()
        st.subheader("➕ Ajouter un nouveau compte")
        with st.form("admin_form"):
            col1, col2 = st.columns(2)
            id_a = col1.text_input("Identifiant")
            mdp_a = col1.text_input("Mot de passe")
            ville_a = col2.text_input("Ville")
            lat = col2.number_input("Lat (ex: 7.18)", format="%.4f")
            lon = col2.number_input("Lon (ex: -7.45)", format="%.4f")
            if st.form_submit_button("Ajouter"):
                u_new = pd.DataFrame({"identifiant": [id_a], "mot_de_passe": [mdp_a], "ville": [ville_a], "role": ["agent"]})
                pd.concat([u_df, u_new]).to_csv("utilisateurs.csv", index=False)
                v_df = charger_villes_coords()
                v_new = pd.DataFrame({"Ville": [ville_a], "Lat": [lat], "Lon": [lon]})
                pd.concat([v_df, v_new]).drop_duplicates(subset="Ville").to_csv("villes_ci.csv", index=False)
                st.success(f"Compte pour {ville_a} créé !")
                st.rerun()