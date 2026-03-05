import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. Configuration de la page
st.set_page_config(page_title="SODEXAM - ClimatoPluvio", layout="wide")

# 2. Connexion au Google Sheet (utilise l'URL mis dans les Secrets)
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Chargement des données
try:
    df_releves = conn.read(worksheet="relevés")
    df_users = conn.read(worksheet="utilisateurs")
except:
    st.error("Erreur de connexion au Google Sheet. Vérifiez vos Secrets Streamlit.")
    st.stop()

st.title("🌧️ SODEXAM : Gestion des Pluies")

# 4. Formulaire de Saisie (Station Abidjan par défaut)
with st.sidebar:
    st.header("📝 Nouveau Relevé")
    date = st.date_input("Date")
    pluie = st.number_input("Pluie (mm)", min_value=0.0, step=0.1)
    obs = st.text_area("Observations")
    
    if st.button("Enregistrer sur le Cloud"):
        # Préparation de la nouvelle ligne
        new_data = pd.DataFrame([{
            "Date_Heure": str(date),
            "Station": "Abidjan",
            "Pluie (mm)": pluie,
            "Obs": obs,
            "Lat": 5.3364,
            "Lon": -4.0267
        }])
        # Envoi vers Google Sheets
        updated_df = pd.concat([df_releves, new_data], ignore_index=True)
        conn.update(worksheet="relevés", data=updated_df)
        st.success("Donnée enregistrée dans votre Google Sheet !")
        st.rerun()

# 5. Affichage et Export pour Surfer 13
st.subheader("📊 Historique et Exportation GIS")
if not df_releves.empty:
    st.write("Cochez les lignes pour l'exportation vers Surfer 13 :")
    df_releves.insert(0, "Sélection", False)
    
    # Éditeur de tableau
    edited_df = st.data_editor(df_releves, hide_index=True)
    
    # Filtrer pour l'exportation
    to_export = edited_df[edited_df["Sélection"] == True]
    
    if not to_export.empty:
        csv = to_export[["Lon", "Lat", "Pluie (mm)"]].to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger le fichier pour Surfer 13", data=csv, file_name="data_sodexam_surfer.csv")
else:
    st.info("Aucune donnée dans le tableau Google Sheet pour le moment.")
