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
st.set_page_config(page_title="SODEXAM - Direction Technique", layout="wide", page_icon="🌧️")

# Création des dossiers de stockage si absents
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
    # Admin par défaut si fichier inexistant
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
    # --- CONFIGURATION EMAIL (À remplir avec vos accès) ---
    expediteur = "votre_email@gmail.com" 
    mot_de_passe = "votre_code_application" 
    
    msg = MIMEMultipart()
    msg['From'] = expediteur
    msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - Rapport Hebdomadaire {datetime.now().strftime('%d/%m/%Y')}"
    
    corps = "Bonjour,\n\nVeuillez trouver ci-joint l'archive ZIP contenant les relevés de toutes les localités.\n\nCordialement,\nSystème SODEXAM."
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
    # --- BARRE LATÉRALE ---
    st.sidebar.title("SODEXAM")
    
    # Affichage du logo avec gestion d'erreur améliorée
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png", use_container_width=True)
    else:
        st.sidebar.warning("Logo introuvable (logo.png)")

    st.sidebar.write(f"Utilisateur : **{st.session_state.user_ville}** ({st.session_state.user_role})")
    
    options = ["Carte Nationale", "Saisie Relevé", "Historique"]
    if st.session_state.user_role == "admin":
        options.insert(1, "📊 Dashboard Admin")
        options.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Menu", options)
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 1. CARTE NATIONALE ---
    if choix == "Carte Nationale":
        st.header("📍 Réseau Pluviométrique")
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

    # --- 2. DASHBOARD ADMIN (LECTURE + ARCHIVAGE + PURGE) ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Supervision & Maintenance (ADMIN)")
        fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
        
        if fichiers:
            # Consolidation de toutes les données pour lecture
            all_dfs = [pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers]
            df_national = pd.concat(all_dfs).sort_values(by="Date_Heure", ascending=False)
            
            # Lecture interactive
            st.subheader("👀 Lecture des données nationales")
            filtre = st.multiselect("Filtrer par localité", options=df_national['Ville'].unique())
            df_affiche = df_national if not filtre else df_national[df_national['Ville'].isin(filtre)]
            st.dataframe(df_affiche, use_container_width=True, height=350)

            # Archivage et Purge
            st.divider()
            st.subheader("📧 Maintenance Hebdomadaire")
            dest = st.text_input("Email du destinataire", "direction@sodexam.ci")
            c1, c2 = st.columns(2)
            
            if c1.button("📨 1. Envoyer ZIP par Mail", use_container_width=True, type="primary"):
                nom_zip = f"Sodexam_Hebdo_{datetime.now().strftime('%d-%m-%Y')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in fichiers: z.write(os.path.join("Donnees_Villes", f), f)
                try:
                    envoyer_email_archive(dest, nom_zip)
                    st.session_state.save_success = True
                    st.success("Archive envoyée ! Vous pouvez maintenant purger.")
                except Exception as e: st.error(f"Erreur d'envoi: {e}")

            if c2.button("🗑️ 2. Purger le système", use_container_width=True, disabled=not st.session_state.save_success):
                for f in fichiers: os.remove(os.path.join("Donnees_Villes", f))
                st.session_state.save_success = False
                st.success("Purge terminée. Les dossiers sont vides.")
                st.rerun()
        else: st.info("Aucune donnée disponible.")

    # --- 3. SAISIE RELEVÉ ---
    elif choix == "Saisie Relevé":
        st.header(f"Saisie : {st.session_state.user_ville}")
        with st.form("saisie"):
            col1, col2 = st.columns(2)
            d = col1.date_input("Date")
            h = col2.time_input("Heure")
            p = st.number_input("Pluviométrie (mm)", min_value=0.0, step=0.1)
            o = st.text_area("Observations")
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                timestamp = f"{d} {h.strftime('%H:%M')}"
                new_data = pd.DataFrame({"Date_Heure": [timestamp], "Pluie (mm)": [p], "Observations": [o]})
                if os.path.exists(path): new_data.to_csv(path, mode='a', header=False, index=False)
                else: new_data.to_csv(path, index=False)
                st.success("Relevé enregistré avec succès !")

    # --- 4. HISTORIQUE (ADAPTATIF ADMIN / AGENT) ---
    elif choix == "Historique":
        if st.session_state.user_role == "admin":
            st.header("📚 Historique Global (Tous les comptes)")
            fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
            if fichiers:
                all_data = pd.concat([pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers])
                all_data = all_data.sort_values(by="Date_Heure", ascending=False)
                st.dataframe(all_data, use_container_width=True)
                st.download_button("📥 Télécharger Historique Global CSV", all_data.to_csv(index=False).encode('utf-8'), "historique_complet.csv")
            else: st.info("Aucun historique disponible.")
        else:
            st.header(f"Historique Station : {st.session_state.user_ville}")
            path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                df.insert(0, "Sélection", False)
                edited = st.data_editor(df, hide_index=True, use_container_width=True)
                if st.button("❌ Supprimer les lignes sélectionnées"):
                    df_final = edited[edited["Sélection"] == False].drop(columns=["Sélection"])
                    df_final.to_csv(path, index=False)
                    st.rerun()
            else: st.info("Aucune donnée enregistrée.")

    # --- 5. GESTION DES COMPTES (ADMIN) ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("Gestion des Agents et Stations")
        with st.form("admin_form"):
            col1, col2 = st.columns(2)
            id_a = col1.text_input("Identifiant Agent")
            mdp_a = col1.text_input("Mot de passe")
            ville_a = col2.text_input("Ville")
            lat_a = col2.number_input("Latitude", format="%.4f")
            lon_a = col2.number_input("Longitude", format="%.4f")
            if st.form_submit_button("Ajouter la station au réseau"):
                u_df = charger_utilisateurs()
                u_new = pd.DataFrame({"identifiant": [id_a], "mot_de_passe": [mdp_a], "ville": [ville_a], "role": ["agent"]})
                pd.concat([u_df, u_new]).to_csv("utilisateurs.csv", index=False)
                v_df = charger_villes_coords()
                v_new = pd.DataFrame({"Ville": [ville_a], "Lat": [lat_a], "Lon": [lon_a]})
                pd.concat([v_df, v_new]).drop_duplicates(subset="Ville").to_csv("villes_ci.csv", index=False)
                st.success(f"Compte et station pour {ville_a} activés !")