import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import zipfile
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SODEXAM - Gestion Pluviométrique", layout="wide", page_icon="🌧️")

if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# --- LOGIQUE SYNOPTIQUE (18h + 08h) ---
def calculer_journee_meteo(df):
    if df.empty: return df
    df = df.copy()
    df['Date_Heure'] = pd.to_datetime(df['Date_Heure'])
    # Règle : Après 18h, le relevé compte pour le lendemain
    df['Jour_Meteo'] = df.apply(
        lambda x: (x['Date_Heure'].date() + timedelta(days=1)) if x['Date_Heure'].hour >= 18 
        else x['Date_Heure'].date(), axis=1
    )
    return df

# --- FONCTIONS TECHNIQUES ---
def charger_utilisateurs():
    nom_f = "utilisateurs.csv"
    if os.path.exists(nom_f):
        try: return pd.read_csv(nom_f)
        except: pass
    df = pd.DataFrame({"identifiant": ["admin"], "mot_de_passe": ["admin123"], "ville": ["Abidjan"], "role": ["admin"]})
    df.to_csv(nom_f, index=False)
    return df

def charger_villes_coords():
    nom_f = "villes_ci.csv"
    if os.path.exists(nom_f):
        try: return pd.read_csv(nom_f)
        except: pass
    df = pd.DataFrame({"Ville": ["Abidjan"], "Lat": [5.309], "Lon": [-4.012]})
    df.to_csv(nom_f, index=False)
    return df

def envoyer_email_archive(destinataire, fichier_zip):
    expediteur = "lateseraphinkone@gmail.com" 
    mot_de_passe = "wdgu cdog ddjp gxlw" 
    msg = MIMEMultipart()
    msg['From'] = expediteur
    msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - Rapport Pluviométrique {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText("Archive des relevés jointe.", 'plain'))
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

# --- AUTHENTIFICATION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM - SYSTÈME PLUVIO</h1>", unsafe_allow_html=True)
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
    # --- BARRE LATÉRALE AVEC LOGO ---
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png", use_container_width=True)
    else:
        st.sidebar.markdown("<h2 style='color: #004a99;'>SODEXAM</h2>", unsafe_allow_html=True)
    
    st.sidebar.write(f"📍 Station: **{st.session_state.user_ville}**")
    
    menu = ["Carte Nationale", "Saisie Relevé", "Historique"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin")
        menu.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Navigation", menu)
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 1. CARTE ---
    if choix == "Carte Nationale":
        st.header("📍 État du Réseau")
        villes_df = charger_villes_coords()
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        for _, v in villes_df.iterrows():
            path = f"Donnees_Villes/{v['Ville']}.csv"
            color = "blue"
            if os.path.exists(path): color = "green"
            folium.Marker([v['Lat'], v['Lon']], popup=v['Ville'], icon=folium.Icon(color=color)).add_to(m)
        st_folium(m, width="100%", height=500)

    # --- 2. DASHBOARD ADMIN (MASSE D'EAU) ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Masse d'eau Mensuelle (Règle 18h+08h)")
        fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
        if fichiers:
            df_glob = pd.concat([pd.read_csv(f"Donnees_Villes/{f}").assign(Ville=f.replace(".csv","")) for f in fichiers])
            df_meteo = calculer_journee_meteo(df_glob)
            
            stats = []
            for ville in df_meteo['Ville'].unique():
                df_v = df_meteo[df_meteo['Ville'] == ville]
                jours = df_v.groupby('Jour_Meteo')['Pluie (mm)'].sum().reset_index()
                stats.append({
                    "Zone": ville,
                    "Masse Totale (mm)": round(jours['Pluie (mm)'].sum(), 2),
                    "Max Journalier": round(jours['Pluie (mm)'].max(), 2)
                })
            st.table(pd.DataFrame(stats).sort_values("Masse Totale (mm)", ascending=False))
            
            dest = st.text_input("Envoyer à:", "direction@sodexam.ci")
            if st.button("📨 Envoyer Archive ZIP"):
                nom_zip = f"Archive_{datetime.now().strftime('%Y%m%d')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in fichiers: z.write(os.path.join("Donnees_Villes", f), f)
                envoyer_email_archive(dest, nom_zip)
                st.success("Envoyé !")
        else: st.info("Aucune donnée.")

    # --- 3. SAISIE RELEVÉ (MULTI-SÉLECTION) ---
    elif choix == "Saisie Relevé":
        st.header(f"Saisie : {st.session_state.user_ville}")
        with st.form("form_saisie"):
            d = st.date_input("Date")
            h = st.radio("Heure", ["08:00", "18:00", "Autre"], horizontal=True)
            p = st.number_input("Pluviométrie (mm)", min_value=0.0)
            
            st.markdown("### ☁️ Phénomènes observés")
            # MULTI-SÉLECTION ICI
            phens = st.multiselect("Sélectionnez les phénomènes", 
                                  ["🌧️ Pluie", "⚡ Éclairs", "⛈️ Orage", "🌫️ Brouillard", "💨 Vent fort", "☀️ Ensoleillé"])
            
            inten = st.select_slider("Intensité", ["Faible", "Modérée", "Forte", "Violente"])
            
            c1, c2 = st.columns(2)
            h_d = c1.text_input("Heure début (HH:MM)")
            h_f = c2.text_input("Heure fin (HH:MM)")
            
            notes = st.text_area("Notes complémentaires")
            
            if st.form_submit_button("Enregistrer"):
                obs_final = f"[{', '.join(phens)}] Intensité: {inten} | De {h_d} à {h_f} | Obs: {notes}"
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                df_new = pd.DataFrame({"Date_Heure": [f"{d} {h}"], "Pluie (mm)": [p], "Observations": [obs_final]})
                df_new.to_csv(path, mode='a', header=not os.path.exists(path), index=False)
                st.success("Relevé enregistré !")

    # --- 4. HISTORIQUE ---
    elif choix == "Historique":
        st.header("📚 Historique")
        ville = st.session_state.user_ville
        if st.session_state.user_role == "admin":
            f_list = [f.replace(".csv","") for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
            ville = st.selectbox("Zone", f_list)
        
        path_h = f"Donnees_Villes/{ville}.csv"
        if os.path.exists(path_h):
            df_h = pd.read_csv(path_h)
            st.data_editor(df_h, use_container_width=True)
        else: st.info("Pas de données.")

    # --- 5. GESTION COMPTES ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("⚙️ Paramétrage")
        u_df = charger_utilisateurs()
        st.dataframe(u_df, use_container_width=True)
        with st.form("add_u"):
            st.write("Ajouter une station")
            c1, c2 = st.columns(2)
            nid, npw = c1.text_input("Identifiant"), c1.text_input("Pass")
            nvi, nla, nlo = c2.text_input("Ville"), c2.number_input("Lat"), c2.number_input("Lon")
            if st.form_submit_button("Créer"):
                pd.concat([u_df, pd.DataFrame({"identifiant":[nid],"mot_de_passe":[npw],"ville":[nvi],"role":["agent"]})]).to_csv("utilisateurs.csv", index=False)
                v_df = charger_villes_coords()
                pd.concat([v_df, pd.DataFrame({"Ville":[nvi],"Lat":[nla],"Lon":[nlon]})]).to_csv("villes_ci.csv", index=False)
                st.rerun()