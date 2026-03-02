import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os
import zipfile
import smtplib
import io
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SODEXAM - Système Intégré", layout="wide", page_icon="🌧️")

if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# --- 2. FONCTION ENVOI EMAIL ---
def envoyer_email_archive(destinataire, fichier_zip, periode_str):
    # --- CONFIGURATION À REMPLIR ---
    expediteur = "lateseraphinkone@gmail.com" 
    mot_de_passe_app = "wdgu cdog ddjp gxlw" 
    # -------------------------------
    
    msg = MIMEMultipart()
    msg['From'] = expediteur
    msg['To'] = destinataire
    msg['Subject'] = f"SODEXAM - ARCHIVE PLUVIO : {periode_str}"
    
    corps = f"Bonjour,\n\nCi-joint l'archive des relevés pluviométriques pour la période : {periode_str}.\n\nCordialement,\nDirection Technique SODEXAM."
    msg.attach(MIMEText(corps, 'plain'))
    
    try:
        with open(fichier_zip, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {fichier_zip}")
            msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(expediteur, mot_de_passe_app)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi : {e}")
        return False

# --- 3. CHARGEMENT DES DONNÉES ---
def charger_toutes_donnees():
    fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
    if not fichiers: return pd.DataFrame()
    all_dfs = [pd.read_csv(os.path.join("Donnees_Villes", f)).assign(Ville=f.replace(".csv","")) for f in fichiers]
    df = pd.concat(all_dfs)
    df['Date_Heure'] = pd.to_datetime(df['Date_Heure'])
    return df

def charger_utilisateurs():
    if os.path.exists("utilisateurs.csv"): return pd.read_csv("utilisateurs.csv")
    df = pd.DataFrame({"identifiant": ["admin"], "mot_de_passe": ["admin123"], "ville": ["Abidjan"], "role": ["admin"]})
    df.to_csv("utilisateurs.csv", index=False)
    return df

# --- 4. AUTHENTIFICATION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False

if not st.session_state.connecte:
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM - ACCÈS</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        u = st.text_input("Identifiant").strip()
        p = st.text_input("Mot de passe", type="password").strip()
        if st.button("Se connecter", use_container_width=True):
            users = charger_utilisateurs()
            user = users[(users['identifiant'].astype(str) == u) & (users['mot_de_passe'].astype(str) == p)]
            if not user.empty:
                st.session_state.update({"connecte": True, "user_ville": user.iloc[0]['ville'], "user_role": user.iloc[0]['role']})
                st.rerun()
            else: st.error("Accès refusé.")
else:
    # --- BARRE LATÉRALE ---
    if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
    
    menu = ["🌍 Carte du Réseau", "📝 Saisie Relevé", "📚 Historique", "📈 Analyses & Graphiques"]
    if st.session_state.user_role == "admin":
        menu.insert(1, "📊 Dashboard Admin")
        menu.append("⚙️ Gestion Comptes")
    
    choix = st.sidebar.radio("Navigation", menu)
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # --- 📈 SECTION ANALYSES & GRAPHIQUES ---
    if choix == "📈 Analyses & Graphiques":
        st.header("📈 Comparaison et Tendances")
        df_total = charger_toutes_donnees()
        if not df_total.empty:
            villes_sel = st.multiselect("Comparer les villes", df_total['Ville'].unique(), default=df_total['Ville'].unique()[:2])
            annee_sel = st.selectbox("Année", sorted(df_total['Date_Heure'].dt.year.unique(), reverse=True))
            
            df_plot = df_total[(df_total['Ville'].isin(villes_sel)) & (df_total['Date_Heure'].dt.year == annee_sel)]
            
            # Courbe d'évolution
            fig = px.line(df_plot, x='Date_Heure', y='Pluie (mm)', color='Ville', title=f"Évolution {annee_sel}")
            st.plotly_chart(fig, use_container_width=True)
            
            # Cumul total par ville
            st.subheader("Cumul total par station")
            df_sum = df_plot.groupby('Ville')['Pluie (mm)'].sum().reset_index()
            fig_bar = px.bar(df_sum, x='Ville', y='Pluie (mm)', color='Ville', text_auto='.1f')
            st.plotly_chart(fig_bar, use_container_width=True)
        else: st.info("Aucune donnée à analyser.")

    # --- 📊 DASHBOARD ADMIN (FILTRES ANNEE/MOIS & EMAIL) ---
    elif choix == "📊 Dashboard Admin":
        st.header("📊 Administration & Exports")
        df_total = charger_toutes_donnees()
        if not df_total.empty:
            c1, c2 = st.columns(2)
            an_sel = c1.selectbox("Année", ["Toutes"] + list(df_total['Date_Heure'].dt.year.unique()))
            mo_sel = c2.selectbox("Mois", ["Tous", "Janv", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"])
            
            st.divider()
            email_dest = st.text_input("Envoyer l'archive à :", "direction@sodexam.ci")
            if st.button("📦 Générer et Envoyer l'archive ZIP", type="primary"):
                nom_zip = f"Export_SODEXAM_{datetime.now().strftime('%H%M')}.zip"
                with zipfile.ZipFile(nom_zip, 'w') as z:
                    for f in os.listdir("Donnees_Villes"):
                        z.write(os.path.join("Donnees_Villes", f), f)
                
                if envoyer_email_archive(email_dest, nom_zip, f"{mo_sel} {an_sel}"):
                    st.success(f"Archive envoyée avec succès à {email_dest}")
                os.remove(nom_zip)
        else: st.info("Base de données vide.")

    # --- ⚙️ GESTION COMPTES ---
    elif choix == "⚙️ Gestion Comptes":
        st.header("⚙️ Gestion des Comptes")
        u_df = charger_utilisateurs()
        for i, r in u_df.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"👤 **{r['identifiant']}** ({r['ville']})")
            if r['identifiant'] != "admin":
                if col3.button("🗑️", key=f"del_{i}"):
                    u_df.drop(i).to_csv("utilisateurs.csv", index=False)
                    st.rerun()
        
        with st.form("edit_u"):
            st.write("📝 Ajouter / Modifier")
            nid, npw, nvi = st.text_input("ID"), st.text_input("Pass"), st.text_input("Ville")
            if st.form_submit_button("Sauvegarder"):
                if nid in u_df['identifiant'].values:
                    u_df.loc[u_df['identifiant'] == nid, ['mot_de_passe', 'ville']] = [npw, nvi]
                else:
                    u_df = pd.concat([u_df, pd.DataFrame({"identifiant":[nid],"mot_de_passe":[npw],"ville":[nvi],"role":["agent"]})])
                u_df.to_csv("utilisateurs.csv", index=False)
                st.rerun()

    # --- 📝 SAISIE RELEVÉ ---
    elif choix == "📝 Saisie Relevé":
        st.header(f"Saisie Station : {st.session_state.user_ville}")
        with st.form("saisie"):
            d = st.date_input("Date")
            h = st.selectbox("Heure", ["08:00", "18:00"])
            p = st.number_input("Pluie (mm)", min_value=0.0)
            phens = st.multiselect("Phénomènes", ["Pluie", "Orage", "Vent", "Brouillard"])
            if st.form_submit_button("Enregistrer"):
                path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                pd.DataFrame({"Date_Heure":[f"{d} {h}"], "Pluie (mm)":[p], "Obs":[str(phens)]}).to_csv(path, mode='a', header=not os.path.exists(path), index=False)
                st.success("Donnée enregistrée !")

    # --- 🌍 CARTE ---
    elif choix == "🌍 Carte du Réseau":
        st.header("🌍 Carte Nationale")
        m = folium.Map(location=[7.5, -5.5], zoom_start=7)
        st_folium(m, width="100%", height=500)

    # --- 📚 HISTORIQUE ---
    elif choix == "📚 Historique":
        st.header("📚 Historique")
        path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
        if os.path.exists(path):
            st.dataframe(pd.read_csv(path), use_container_width=True)
        else: st.info("Aucune donnée.")