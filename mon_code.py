import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SODEXAM - Gestion Pluviométrique", layout="wide")

st.title("🌧️ SODEXAM : Système de Collecte (Climato)")
st.markdown("---")

# --- CONNEXION AU GOOGLE SHEET ---
# Note : Assurez-vous que l'onglet s'appelle exactement 'relevés' dans Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Lecture des données existantes
    df = conn.read(worksheet="relevés")
except Exception as e:
    st.error("⚠️ Erreur de connexion au Google Sheet.")
    st.info("Vérifiez que l'onglet en bas de votre Google Sheet s'appelle exactement : relevés")
    st.stop()

# --- BARRE LATÉRALE : SAISIE DES DONNÉES ---
with st.sidebar:
    st.header("📝 Nouveau Relevé")
    
    # Liste des stations (vous pouvez en ajouter d'autres ici)
    station = st.selectbox("Station", ["Abidjan", "Bouaké", "Korhogo", "San-Pédro", "Man"])
    
    # Coordonnées automatiques pour Surfer 13
    coords = {
        "Abidjan": [5.3364, -4.0267],
        "Bouaké": [7.6939, -5.0303],
        "Korhogo": [9.4580, -5.6290],
        "San-Pédro": [4.7485, -6.6363],
        "Man": [7.4125, -7.5538]
    }
    
    date_releve = st.date_input("Date du relevé")
    valeur_pluie = st.number_input("Pluie (mm)", min_value=0.0, step=0.1, format="%.1f")
    observation = st.text_input("Observation", "RAS")

    if st.button("Enregistrer la donnée"):
        # Préparation de la nouvelle ligne
        lat_lon = coords.get(station, [0.0, 0.0])
        nouvelle_ligne = pd.DataFrame([{
            "Date_Heure": str(date_releve),
            "Station": station,
            "Pluie (mm)": valeur_pluie,
            "Obs": observation,
            "Lat": lat_lon[0],
            "Lon": lat_lon[1]
        }])
        
        # Mise à jour du Google Sheet
        df_final = pd.concat([df, nouvelle_ligne], ignore_index=True)
        conn.update(worksheet="relevés", data=df_final)
        
        st.success(f"✅ Donnée de {station} enregistrée !")
        st.rerun()

# --- AFFICHAGE ET EXPORTATION POUR SURFER 13 ---
st.subheader("📊 Visualisation des données")

if not df.empty:
    # Affichage du tableau
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("🗺️ Préparation pour Surfer 13")
    st.write("Ce bouton génère le fichier CSV (Lon, Lat, Pluie) prêt pour le Gridding.")
    
    # Création du fichier spécifique pour Surfer (Format: X, Y, Z)
    df_surfer = df[['Lon', 'Lat', 'Pluie (mm)']]
    csv_data = df_surfer.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Télécharger le fichier pour SURFER 13",
        data=csv_data,
        file_name="data_sodexam_surfer.csv",
        mime="text/csv"
    )
else:
    st.warning("Le tableau est vide. Veuillez saisir une première donnée dans la barre latérale.")
