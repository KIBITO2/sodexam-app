import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="SODEXAM - Réseau National", layout="wide", page_icon="🌧️")

# Création du dossier de stockage si absent
if not os.path.exists("Donnees_Villes"):
    os.makedirs("Donnees_Villes")

# --- FONCTIONS DE CHARGEMENT SÉCURISÉES ---

def charger_utilisateurs():
    nom_f = "utilisateurs.csv"
    admin_defaut = pd.DataFrame({
        "identifiant": ["admin"], 
        "mot_de_passe": ["admin123"], 
        "ville": ["Abidjan"], 
        "role": ["admin"]
    })
    if os.path.exists(nom_f):
        try:
            # sep=None permet de détecter , ou ; automatiquement
            df = pd.read_csv(nom_f, sep=None, engine='python')
            if 'identifiant' in df.columns and 'mot_de_passe' in df.columns:
                return df
        except:
            pass
    # Si erreur ou fichier mal formé, on recrée un propre
    admin_defaut.to_csv(nom_f, index=False)
    return admin_defaut

def charger_villes_coords():
    nom_f = "villes_ci.csv"
    villes_defaut = pd.DataFrame({
        "Ville": ["Abidjan", "Yamoussoukro", "Bouaké", "San-Pédro", "Korhogo", "Tabou", "Facobly"],
        "Lat": [5.3096, 6.8276, 7.6934, 4.7485, 9.4580, 4.4229, 7.1869],
        "Lon": [-4.0127, -5.2767, -5.0303, -6.6363, -5.6296, -7.3528, -7.4569]
    })
    if os.path.exists(nom_f):
        try:
            df = pd.read_csv(nom_f, sep=None, engine='python')
            if 'Ville' in df.columns and 'Lat' in df.columns:
                return df
        except:
            pass
    villes_defaut.to_csv(nom_f, index=False)
    return villes_defaut

# --- INITIALISATION ---
if 'connecte' not in st.session_state:
    st.session_state.connecte = False
    st.session_state.user_ville = ""
    st.session_state.user_role = ""

# --- ÉCRAN DE CONNEXION ---
def ecran_connexion():
    st.markdown("<h1 style='text-align: center; color: #004a99;'>SODEXAM</h1>", unsafe_allow_html=True)
    st.subheader("Connexion au Réseau National de Pluviométrie")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("form_login"):
            id_user = st.text_input("Identifiant")
            mdp_user = st.text_input("Mot de passe", type="password")
            valider = st.form_submit_button("Se connecter", use_container_width=True)
            
            if valider:
                users = charger_utilisateurs()
                # Nettoyage des espaces pour éviter les erreurs de frappe
                users['identifiant'] = users['identifiant'].astype(str).str.strip()
                user = users[(users['identifiant'] == id_user.strip()) & (users['mot_de_passe'].astype(str) == mdp_user.strip())]
                
                if not user.empty:
                    st.session_state.connecte = True
                    st.session_state.user_ville = user.iloc[0]['ville']
                    st.session_state.user_role = user.iloc[0]['role']
                    st.rerun()
                else:
                    st.error("Identifiants incorrects. Vérifiez l'orthographe.")

# --- INTERFACE APPRÈS CONNEXION ---
if not st.session_state.connecte:
    ecran_connexion()
else:
    # Sidebar
    st.sidebar.title("MENU")
    if os.path.exists("app (1).png.png"):
        st.sidebar.image("app (1).png.png")
    
    st.sidebar.info(f"Ville : {st.session_state.user_ville}\nRôle : {st.session_state.user_role}")
    
    option = st.sidebar.radio("Navigation", ["Carte Nationale", "Saisie Journalière", "Historique & Suppression", "Admin (Gestion)"])
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.connecte = False
        st.rerun()

    # 1. CARTE NATIONALE
    if option == "Carte Nationale":
        st.header("📍 État du Réseau")
        villes_df = charger_villes_coords()
        m = folium.Map(location=[7.5399, -5.5471], zoom_start=7)
        
        for _, v in villes_df.iterrows():
            path = f"Donnees_Villes/{v['Ville']}.csv"
            color = "blue"
            popup_txt = f"<b>{v['Ville']}</b><br>Aucune donnée"
            
            if os.path.exists(path):
                data = pd.read_csv(path)
                if not data.empty:
                    val = data.iloc[-1]['Pluie (mm)']
                    popup_txt = f"<b>{v['Ville']}</b><br>Dernier relevé: {val} mm"
                    color = "green" if val < 50 else "red"
            
            folium.Marker([v['Lat'], v['Lon']], popup=popup_txt, icon=folium.Icon(color=color)).add_to(m)
        
        st_folium(m, width="100%", height=550)

    # 2. SAISIE DES DONNÉES
    elif option == "Saisie Journalière":
        st.header(f"Saisie pour {st.session_state.user_ville}")
        with st.form("saisie_pluie"):
            date_p = st.date_input("Date", datetime.now())
            valeur = st.number_input("Pluviométrie (mm)", min_value=0.0, step=0.1)
            obs = st.text_area("Observations")
            if st.form_submit_button("Enregistrer"):
                f_path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
                new_row = pd.DataFrame({"Date": [date_p], "Pluie (mm)": [valeur], "Observations": [obs]})
                if os.path.exists(f_path):
                    new_row.to_csv(f_path, mode='a', header=False, index=False)
                else:
                    new_row.to_csv(f_path, index=False)
                st.success("Donnée enregistrée avec succès !")

    # 3. HISTORIQUE AVEC CASES À COCHER POUR SUPPRESSION
    elif option == "Historique & Suppression":
        st.header(f"Historique de {st.session_state.user_ville}")
        f_path = f"Donnees_Villes/{st.session_state.user_ville}.csv"
        
        if os.path.exists(f_path):
            df = pd.read_csv(f_path)
            if not df.empty:
                st.write("Cochez les lignes pour les supprimer :")
                df_edit = df.copy()
                df_edit.insert(0, "Sélection", False)
                
                edited = st.data_editor(df_edit, hide_index=True, use_container_width=True,
                                      column_config={"Sélection": st.column_config.CheckboxColumn(required=True)})
                
                if st.button("❌ Supprimer la sélection"):
                    df_final = edited[edited["Sélection"] == False].drop(columns=["Sélection"])
                    df_final.to_csv(f_path, index=False)
                    st.success("Mise à jour effectuée !")
                    st.rerun()
            else:
                st.info("Aucune donnée.")
        else:
            st.info("Le fichier n'existe pas encore.")

    # 4. GESTION ADMIN (Ajout de villes et utilisateurs)
    elif option == "Admin (Gestion)":
        if st.session_state.user_role != "admin":
            st.error("Réservé à l'Admin.")
        else:
            st.subheader("Ajouter une ville ou une sous-préfecture")
            with st.form("new_user"):
                new_id = st.text_input("Identifiant Agent")
                new_mdp = st.text_input("Mot de passe")
                new_v = st.text_input("Nom de la Ville")
                n_lat = st.number_input("Latitude", format="%.4f")
                n_lon = st.number_input("Longitude", format="%.4f")
                
                if st.form_submit_button("Créer le compte et la ville"):
                    # Maj utilisateurs
                    u_df = charger_utilisateurs()
                    u_new = pd.DataFrame({"identifiant": [new_id], "mot_de_passe": [new_mdp], "ville": [new_v], "role": ["agent"]})
                    pd.concat([u_df, u_new]).to_csv("utilisateurs.csv", index=False)
                    # Maj coordonnées
                    v_df = charger_villes_coords()
                    v_new = pd.DataFrame({"Ville": [new_v], "Lat": [n_lat], "Lon": [n_lon]})
                    pd.concat([v_df, v_new]).drop_duplicates(subset="Ville").to_csv("villes_ci.csv", index=False)
                    st.success(f"Ville {new_v} ajoutée au réseau !")