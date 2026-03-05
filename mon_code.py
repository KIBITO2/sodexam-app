import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SODEXAM - Gestion Pluviométrique", layout="wide")

st.title("🌧️ SODEXAM : Système de Collecte (Climato)")
st.markdown("---")

# --- CONNEXION AU GOOGLE SHEET ---
# Utilise la connexion définie dans vos "Secrets" Streamlit
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # MODIFICATION : On lit la première feuille (index 0) pour éviter les erreurs de nom
    df = conn.read(worksheet=0)
except Exception as e:
    st.error("⚠️ Erreur de connexion au Google Sheet.")
    st.info("Vérifiez que vous avez bien collé le lien dans les 'Secrets' sur Streamlit Cloud.")
    st.stop()

# --- BARRE LATÉRALE : SAISIE DES DONNÉES ---
with st.sidebar:
    st.header("📝 Nouveau Relevé")
    
    # Liste des stations majeures de Côte d'Ivoire
    station = st.selectbox("Station", ["Abidjan", "Bouaké", "Korhogo", "San-Pédro", "Man", "Yamoussoukro", "Daloa"])
    
    # Coordonnées automatiques pour Surfer 13 (X, Y)
    coords = {
        "Abidjan": [5.3364, -4.0267],
        "Bouaké": [7.6939, -5.0303],
        "Korhogo": [9.4580, -5.6290],
        "San-Pédro": [4.7485, -6.6363],
        "Man": [7.4125, -7.5538],
        "Yamoussoukro": [6.8276, -5.2743],
        "Daloa": [6.8773, -6.4502]
    }
    
    date_releve = st.date_input("Date du relevé")
    valeur_pluie = st.number_input("Pluie (mm)", min_value=0.0, step=0.1, format="%.1f")
    observation = st.text_input("Observation", "RAS")

    if st.button("Enregistrer la donnée"):
        # Récupération des coordonnées GPS
        lat_lon = coords.get(station, [0.0, 0.0])
        
        # Création de la nouvelle ligne (doit correspondre aux colonnes de votre Google Sheet)
        nouvelle_ligne = pd.DataFrame([{
            "Date_Heure": str(date_releve),
            "Station": station,
            "Pluie (mm)": valeur_pluie,
            "Obs": observation,
            "Lat": lat_lon[0],
            "Lon": lat_lon[1]
        }])
        
        # Fusion et mise à jour du Cloud
        df_final = pd.concat([df, nouvelle_ligne], ignore_index=True)
        conn.update(worksheet=0, data=df_final)
        
        st.success(f"✅ Donnée de {station} enregistrée avec succès !")
        st.rerun()

# --- AFFICHAGE ET EXPORTATION POUR SURFER 13 ---
st.subheader("📊 Visualisation des données enregistrées")

if not df.empty:
    # Affichage du tableau interactif
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("🗺️ Préparation pour SURFER 13")
    st.write("Cliquez ci-dessous pour obtenir le fichier CSV prêt pour le Gridding (Kriging).")
    
    # Création du fichier spécifique (Format: Lon=X, Lat=Y, Pluie=Z)
    # Surfer 13 a besoin de ces 3 colonnes pour tracer les isohyètes
    df_surfer = df[['Lon', 'Lat', 'Pluie (mm)']]
    csv_data = df_surfer.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Télécharger le fichier pour SURFER 13 (.csv)",
        data=csv_data,
        file_name="data_sodexam_surfer.csv",
        mime="text/csv"
    )
else:
    st.warning("La base de données est vide. Saisissez une donnée pour commencer.")
