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

# Création des dossiers
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
    expediteur = "votre_email@gmail.com" 
    mot_de_passe = "votre_code_application" 
    msg = MIMEMultipart()
    msg['From'] = expediteur
    msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - Rapport Hebdo {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText("Archive des relevés hebdomadaires ci-jointe.", 'plain'))
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

# --- SESSION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False
    st.session_state.user_role = ""
    st.session_state.user_ville = ""
    st.session_state.save_success = False

# --- CONNEXION ---
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
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png", use_container_width=True)
    else:
        st.sidebar.warning("Logo introuvable")

    options = ["Carte Nationale", "Saisie Relevé", "Historique"]
    if st.session_state.user_role == "admin":
        options.insert(1, "📊 Dashboard Admin")
        options.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Menu", options)
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 1. CARTE ---
    if choix == "Carte Nationale":
        st.header("📍 État du Réseau National")
        villes_df = charger_villes_coords()
        m = folium.Map(location=[7.5399, -5.5471], zoom_start=7)
        for _, v in villes_df.iterrows():
            path = f"Donnees_Villes/{v['Ville']}.csv"
            color, info = "blue", f"<b>{v['Ville']}</b>"
            if os.path.exists(path):
                df_v = pd.read_csv(path)
                if not df_v.empty:
                    der = df_v.iloc[-1]
                    color = "green" if der['Pluie (mm)'] < 50 else "red"
                    info += f"<br>Le {der['Date_Heure']}<br>Pluie: {der['Pluie (mm)']} mm"
            folium.Marker([v['Lat'], v['Lon']], popup=folium.Popup(info, max_width=200), icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=500)

    # --- 2. DASHBOARD ADMIN ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Supervision & Archivage")
        fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
        if fichiers:
            all_dfs = [pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers]
            df_glob = pd.concat(all_dfs).sort_values(by="Date_Heure", ascending=False)
            st.dataframe(df_glob, use_container_width=True)
            
            st.divider()
            dest = st.text_input("Email Destination", "direction@sodexam.ci")
            c1, c2 = st.columns(2)
            if c1.button("📨 Envoyer Archive ZIP", use_container_width=True, type="primary"):
                nom_zip = f"Archive_{datetime.now().strftime('%d-%m-%Y')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in fichiers: z.write(os.path.join("Donnees_Villes", f), f)
                try:
                    envoyer_email_archive(dest, nom_zip)
                    st.session_state.save_success = True
                    st.success("Mail envoyé !")
                except Exception as e: st.error(f"Erreur: {e}")
            if c2.button("🗑️ Purger le système", use_container_width=True, disabled=not st.session_state.save_success):
                for f in fichiers: os.remove(os.path.join("Donnees_Villes", f))
                st.session_state.save_success = False
                st.success("Données purgées.")
                st.rerun()
        else: st.info("Aucune donnée.")

    # --- 3. SAISIE RELEVÉ (AVEC PHÉNOMÈNES MÉTÉO) ---
    elif choix == "Saisie Relevé":
        st.header(f"Saisie Station : {st.session_state.user_ville}")
        with st.form("form_saisie"):
            d = st.date_input("Date du relevé")
            
            # Heures réglementaires
            h_type = st.radio("Type d'heure", ["Heure réglementaire (08h/18h)", "Heure personnalisée"], horizontal=True)
            if h_type == "Heure réglementaire (08h/18h)":
                heure_finale = st.selectbox("Sélectionnez l'heure de collecte", ["08:00", "18:00"])
            else:
                heure_finale = st.time_input("Choisir une heure précise").strftime('%H:%M')

            p = st.number_input("Pluviométrie (mm)", min_value=0.0, step=0.1)
            
            st.markdown("### ⚡ Observations Phénomènes Météo")
            col_icon, col_intensite = st.columns(2)
            
            phenomene = col_icon.selectbox("Icône Phénomène", 
                ["Pas de phénomène", "🌧️ Pluie", "⚡ Éclairs", "⛈️ Orage", "🌫️ Brouillard", "💨 Vent fort"])
            
            intensite = col_intensite.select_slider("Intensité du phénomène", 
                options=["Faible", "Modérée", "Forte", "Violente"])
            
            col_debut, col_fin = st.columns(2)
            h_debut = col_debut.text_input("Heure début (ex: 14:10)", value="--:--")
            h_fin = col_fin.text_input("Heure fin (ex: 15:30)", value="--:--")
            
            detail_obs = st.text_area("Notes complémentaires")
            
            if st.form_submit_button("Enregistrer le relevé"):
                # Formatage de l'observation
                obs_complete = f"[{phenomene}] Intensité: {intensite} | Début: {h_debut} | Fin: {h_fin} | Note: {detail_obs}"
                
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                timestamp = f"{d} {heure_finale}"
                new_row = pd.DataFrame({"Date_Heure": [timestamp], "Pluie (mm)": [p], "Observations": [obs_complete]})
                
                if os.path.exists(path): new_row.to_csv(path, mode='a', header=False, index=False)
                else: new_row.to_csv(path, index=False)
                st.success(f"Relevé météo enregistré !")

    # --- 4. HISTORIQUE & CORRECTION ---
    elif choix == "Historique":
        if st.session_state.user_role == "admin":
            st.header("📚 Correction & Historique Global")
            fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
            if fichiers:
                ville_select = st.selectbox("Ville à corriger", [f.replace(".csv","") for f in fichiers])
                path_c = f"Donnees_Villes/{ville_select}.csv"
                df_c = pd.read_csv(path_c)
                st.write("Modifiez les cellules puis sauvegardez :")
                df_edite = st.data_editor(df_c, use_container_width=True, num_rows="dynamic")
                if st.button("💾 Sauvegarder les corrections"):
                    df_edite.to_csv(path_c, index=False)
                    st.success(f"Données de {ville_select} mises à jour !")
            else: st.info("Aucune donnée.")
        else:
            st.header(f"Mon Historique ({st.session_state.user_ville})")
            path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
            if os.path.exists(path):
                df = pd.read_csv(path)
                st.dataframe(df, use_container_width=True)
            else: st.info("Aucun historique.")

    # --- 5. GESTION COMPTES ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("Gestion du Réseau")
        u_df = charger_utilisateurs()
        st.dataframe(u_df[['identifiant', 'ville', 'role']], use_container_width=True)
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            id_n, pw_n = c1.text_input("Identifiant"), c1.text_input("Mot de passe")
            vi_n, la_n, lo_n = c2.text_input("Ville"), c2.number_input("Lat", format="%.4f"), c2.number_input("Lon", format="%.4f")
            if st.form_submit_button("Ajouter Station"):
                pd.concat([u_df, pd.DataFrame({"identifiant":[id_n],"mot_de_passe":[pw_n],"ville":[vi_n],"role":["agent"]})]).to_csv("utilisateurs.csv", index=False)
                v_df = charger_villes_coords()
                pd.concat([v_df, pd.DataFrame({"Ville":[vi_n],"Lat":[la_n],"Lon":[lo_n]})]).to_csv("villes_ci.csv", index=False)
                st.success("Compte créé.")
                st.rerun()