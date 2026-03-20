
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import zipfile
import smtplib
import hashlib
import io
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from folium.plugins import MarkerCluster, HeatMap
# Module PDF (doit être dans le même dossier que l'app)
try:
    from pdf_alertes import generer_rapport_alertes_pdf
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

# ============================================================
# 1. CONFIGURATION SYSTÈME
# ============================================================
st.set_page_config(
    page_title="SODEXAM - Gestion Intégrée",
    layout="wide",
    page_icon="🌧️",
    initial_sidebar_state="expanded",
)

# Dossiers requis
for folder in ["Donnees_Villes", "assets"]:
    os.makedirs(folder, exist_ok=True)

# ============================================================
# 2. CONSTANTES & RÉFÉRENTIEL
# ============================================================
SEUIL_ALERTE_MM    = 50.0   # Seuil pluie forte (mm)
SEUIL_VIGILANCE_MM = 20.0   # Seuil vigilance

COORDS_STATIONS = {
    "Abidjan":         [5.3364, -4.0267],
    "Bouaké":          [7.6939, -5.0303],
    "Yamoussoukro":    [6.8276, -5.2767],
    "Korhogo":         [9.4580, -5.6290],
    "San-Pédro":       [4.7485, -6.6363],
    "Man":             [7.4125, -7.5538],
    "Odienné":         [9.5051, -7.5643],
    "Daloa":           [6.8774, -6.4502],
    "Bondoukou":       [8.0402, -2.8001],
    "Ferkessédougou":  [9.5928, -5.1983],
    "Sassandra":       [4.9538, -6.0853],
    "Tabou":           [4.4230, -7.3528],
    "Abengourou":      [6.7271, -3.4958],
    "Divo":            [5.8371, -5.3573],
    "Séguéla":         [7.9558, -6.6729],
}

PHENOMENES_OPTIONS = [
    "Orage", "Vent Fort", "Brume", "Brouillard", "Rosée",
    "Grêle", "Tornade", "Inondation", "Sécheresse"
]

# ============================================================
# 3. CSS PERSONNALISÉ – THÈME SODEXAM
# ============================================================
st.markdown("""
<style>
/* === Palette === */
:root {
    --bleu:    #003f8a;
    --bleu2:   #0066cc;
    --cyan:    #00aaff;
    --vert:    #00b894;
    --orange:  #e17055;
    --rouge:   #d63031;
    --gris:    #f0f4f8;
    --texte:   #2d3436;
}

/* Fond général */
[data-testid="stAppViewContainer"] {background: #f5f7fa;}
[data-testid="stSidebar"]          {background: linear-gradient(180deg, #003f8a 0%, #001f5a 100%);}

/* Textes sidebar */
[data-testid="stSidebar"] * {color: #e8f4ff !important;}
[data-testid="stSidebar"] hr {border-color: rgba(255,255,255,0.2) !important;}

/* Radio sidebar */
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 6px 12px;
    margin: 3px 0;
    display: block;
    transition: background .2s;
}
[data-testid="stSidebar"] .stRadio label:hover {background: rgba(255,255,255,0.18);}

/* Cartes KPI */
.kpi-card {
    background: white;
    border-radius: 14px;
    padding: 18px 22px;
    box-shadow: 0 2px 12px rgba(0,63,138,.10);
    border-left: 5px solid var(--bleu2);
    margin-bottom: 10px;
}
.kpi-card h3 {margin: 0; font-size: 2.1rem; color: var(--bleu);}
.kpi-card p  {margin: 0; color: #636e72; font-size: .85rem; text-transform: uppercase; letter-spacing: .05em;}
.kpi-card.alerte {border-left-color: var(--rouge);}
.kpi-card.vert   {border-left-color: var(--vert);}
.kpi-card.orange {border-left-color: var(--orange);}

/* Badges alerte */
.badge-alerte    {background:#ffeaa7;color:#d35400;padding:4px 10px;border-radius:20px;font-weight:700;font-size:.8rem;}
.badge-vigilance {background:#dfe6e9;color:#2d3436;padding:4px 10px;border-radius:20px;font-weight:600;font-size:.8rem;}
.badge-ok        {background:#d4edda;color:#155724;padding:4px 10px;border-radius:20px;font-weight:600;font-size:.8rem;}

/* Entêtes de sections */
.section-header {
    background: linear-gradient(90deg, #003f8a, #0066cc);
    color: white !important;
    padding: 10px 18px;
    border-radius: 10px;
    margin-bottom: 20px;
    font-size: 1.2rem;
}

/* Bouton principal */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #003f8a, #0066cc);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 4. UTILITAIRES
# ============================================================
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

@st.cache_data(ttl=30)
def charger_utilisateurs() -> pd.DataFrame:
    if os.path.exists("utilisateurs.csv"):
        return pd.read_csv("utilisateurs.csv")
    df = pd.DataFrame({
        "identifiant":  ["admin"],
        "mot_de_passe": [hash_password("admin123")],
        "ville":        ["Abidjan"],
        "role":         ["admin"],
        "email":        ["admin@sodexam.ci"],
    })
    df.to_csv("utilisateurs.csv", index=False)
    return df

@st.cache_data(ttl=30)
def charger_toutes_donnees() -> pd.DataFrame:
    fichiers = [f for f in os.listdir("Donnees_Villes") if f.endswith(".csv")]
    if not fichiers:
        return pd.DataFrame()
    all_dfs = []
    for f in fichiers:
        try:
            tmp = pd.read_csv(os.path.join("Donnees_Villes", f))
            tmp["Ville"] = f.replace(".csv", "")
            all_dfs.append(tmp)
        except Exception:
            pass
    if not all_dfs:
        return pd.DataFrame()
    df = pd.concat(all_dfs, ignore_index=True)
    df["Date_Heure"] = pd.to_datetime(df["Date_Heure"], errors="coerce")
    df = df.dropna(subset=["Date_Heure"]).sort_values("Date_Heure")
    df["Pluie (mm)"] = pd.to_numeric(df.get("Pluie (mm)", 0), errors="coerce").fillna(0)
    return df

def badge_niveau(val_mm: float) -> str:
    if val_mm >= SEUIL_ALERTE_MM:
        return f'<span class="badge-alerte">🚨 ALERTE {val_mm} mm</span>'
    elif val_mm >= SEUIL_VIGILANCE_MM:
        return f'<span class="badge-vigilance">⚠️ VIGILANCE {val_mm} mm</span>'
    return f'<span class="badge-ok">✅ Normal {val_mm} mm</span>'

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Données")
    return buf.getvalue()

def _envoyer_pdf_email(destinataire: str, chemin_pdf: str,
                       sujet: str, corps: str) -> None:
    """Envoie un PDF par email via SMTP Gmail."""
    expediteur       = os.environ.get("SMTP_USER", "votre_mail@gmail.com")
    mot_de_passe_app = os.environ.get("SMTP_PASS", "votre_code_16_lettres")
    msg = MIMEMultipart()
    msg["From"]    = expediteur
    msg["To"]      = destinataire
    msg["Subject"] = f"SODEXAM – {sujet}"
    msg.attach(MIMEText(corps + f"\n\nGénéré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.\n\n— Système SODEXAM", "plain"))
    with open(chemin_pdf, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f"attachment; filename={os.path.basename(chemin_pdf)}")
        msg.attach(part)
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(expediteur, mot_de_passe_app)
        server.send_message(msg)
    st.success("✅ Email avec PDF envoyé avec succès !")


def envoyer_email_archive(destinataire: str, fichier_zip: str, periode_str: str) -> bool:
    # ⚠️  Remplissez ces variables dans vos secrets Streamlit ou variables d'env
    expediteur       = os.environ.get("SMTP_USER", "votre_mail@gmail.com")
    mot_de_passe_app = os.environ.get("SMTP_PASS", "votre_code_16_lettres")
    msg = MIMEMultipart()
    msg["From"]    = expediteur
    msg["To"]      = destinataire
    msg["Subject"] = f"SODEXAM – Archive données : {periode_str}"
    corps = (
        f"Bonjour,\n\nVeuillez trouver ci-joint l'archive des données pluviométriques "
        f"({periode_str}).\n\nRapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.\n\n"
        "— Système SODEXAM"
    )
    msg.attach(MIMEText(corps, "plain"))
    try:
        with open(fichier_zip, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(fichier_zip)}")
            msg.attach(part)
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(expediteur, mot_de_passe_app)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"❌ Erreur envoi mail : {e}")
        return False

def afficher_logo():
    for ext in ["logo.png", "logo.jpg", "logo.jpeg", "LOGO.PNG", "LOGO.JPG"]:
        if os.path.exists(ext):
            st.sidebar.image(ext, use_container_width=True)
            return
    st.sidebar.markdown(
        "<h2 style='text-align:center;color:#7ecfff;letter-spacing:.1em;'>🌧️ SODEXAM</h2>",
        unsafe_allow_html=True,
    )

# ============================================================
# 5. AUTHENTIFICATION
# ============================================================
if "connecte" not in st.session_state:
    st.session_state.connecte = False

if not st.session_state.connecte:
    # ---------- PAGE DE CONNEXION ----------
    col_l, col_c, col_r = st.columns([1, 1.6, 1])
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center;color:#003f8a;'>🌧️ SODEXAM</h1>"
            "<p style='text-align:center;color:#636e72;font-size:1rem;'>"
            "Système de Gestion des Données Pluviométriques</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("#### 🔐 Connexion")
            u = st.text_input("Identifiant", placeholder="Entrez votre identifiant")
            p = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            if st.button("Se connecter", use_container_width=True, type="primary"):
                users = charger_utilisateurs()
                hashed = hash_password(p)
                # Compatibilité anciens comptes (mot de passe en clair)
                user = users[
                    (users["identifiant"].astype(str) == u) &
                    ((users["mot_de_passe"].astype(str) == hashed) |
                     (users["mot_de_passe"].astype(str) == p))
                ]
                if not user.empty:
                    row = user.iloc[0]
                    st.session_state.update({
                        "connecte":   True,
                        "user_ville": row["ville"],
                        "user_role":  row["role"],
                        "username":   row["identifiant"],
                        "user_email": row.get("email", ""),
                    })
                    st.rerun()
                else:
                    st.error("❌ Identifiant ou mot de passe incorrect.")
        st.markdown(
            "<p style='text-align:center;color:#b2bec3;font-size:.8rem;margin-top:16px;'>"
            "Version 2.0 | © SODEXAM 2025</p>",
            unsafe_allow_html=True,
        )

# ============================================================
# 6. APPLICATION PRINCIPALE (utilisateur connecté)
# ============================================================
else:
    role  = st.session_state.user_role
    ville = st.session_state.user_ville

    # -------- BARRE LATÉRALE --------
    afficher_logo()
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='text-align:center;padding:8px;'>"
        f"<b>📍 {ville}</b><br>"
        f"<span style='font-size:.85rem;opacity:.8;'>👤 {st.session_state.username} "
        f"| {role.upper()}</span></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    MENU_AGENT = [
        "🌍 Carte Interactive",
        "📝 Saisie Relevé",
        "📚 Historique & Corrections",
        "📈 Analyses Graphiques",
    ]
    MENU_ADMIN = [
        "🌍 Carte Interactive",
        "📊 Dashboard Admin",
        "📝 Saisie Relevé",
        "📚 Historique & Corrections",
        "📈 Analyses Graphiques",
        "🔴 Rapport PDF Alertes",
        "⚙️ Gestion des Comptes",
    ]
    menu = MENU_ADMIN if role == "admin" else MENU_AGENT
    choix = st.sidebar.radio("Navigation", menu, label_visibility="collapsed")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.connecte = False
        st.rerun()

    # ========================================================
    # PAGE 1 – 🌍 CARTE INTERACTIVE
    # ========================================================
    if choix == "🌍 Carte Interactive":
        st.markdown('<div class="section-header">🌍 État Pluviométrique National – Temps Réel</div>',
                    unsafe_allow_html=True)

        df_total = charger_toutes_donnees()

        # Filtres rapides
        fc1, fc2, fc3 = st.columns(3)
        afficher_heatmap = fc1.toggle("🌡️ Carte de chaleur", value=False)
        afficher_clusters = fc2.toggle("🔵 Regrouper marqueurs", value=False)
        nb_jours_carte = fc3.slider("Derniers N jours", 1, 30, 7)

        # Construction de la carte Folium
        m = folium.Map(location=[7.5, -5.5], zoom_start=7,
                       tiles="CartoDB positron")

        heat_data  = []
        dest_layer = MarkerCluster().add_to(m) if afficher_clusters else m

        for v, coords in COORDS_STATIONS.items():
            color, info, pluie_val = "gray", f"<b>{v}</b><br>Aucune donnée.", 0

            if not df_total.empty:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=nb_jours_carte)
                dv = df_total[(df_total["Ville"] == v) & (df_total["Date_Heure"] >= cutoff)]
                if not dv.empty:
                    last      = dv.sort_values("Date_Heure").iloc[-1]
                    cumul     = dv["Pluie (mm)"].sum()
                    pluie_val = last["Pluie (mm)"]
                    phenom    = last.get("Phenomenes", "RAS") or "RAS"

                    if pluie_val >= SEUIL_ALERTE_MM:
                        color = "red"
                    elif pluie_val >= SEUIL_VIGILANCE_MM:
                        color = "orange"
                    elif pluie_val > 0:
                        color = "blue"
                    else:
                        color = "green"

                    info = (
                        f"<b style='font-size:1.05em'>{v}</b><br>"
                        f"📅 Dernier relevé : {last['Date_Heure'].strftime('%d/%m %H:%M')}<br>"
                        f"🌧️ Pluie : <b>{pluie_val} mm</b><br>"
                        f"📦 Cumul {nb_jours_carte}j : <b>{cumul:.1f} mm</b><br>"
                        f"🌪️ Phénomène : {phenom}"
                    )
                    heat_data.append([coords[0], coords[1], pluie_val])

            folium.Marker(
                location=coords,
                popup=folium.Popup(info, max_width=300),
                tooltip=f"{v} – {pluie_val} mm",
                icon=folium.Icon(color=color, icon="tint", prefix="fa"),
            ).add_to(dest_layer)

        if afficher_heatmap and heat_data:
            HeatMap(heat_data, radius=35, blur=20, min_opacity=0.3).add_to(m)

        # Légende
        legend_html = """
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                    padding:12px 16px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.2);font-size:.85rem;">
            <b>Légende</b><br>
            🔴 Alerte (&ge;50 mm) &nbsp; 🟠 Vigilance (&ge;20 mm)<br>
            🔵 Pluie légère &nbsp; 🟢 Sec &nbsp; ⚫ Aucune donnée
        </div>"""
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, width="100%", height=560)

        # Tableau récapitulatif rapide
        if not df_total.empty:
            st.markdown("##### 📋 Résumé des dernières 24 h")
            cutoff24 = pd.Timestamp.now() - pd.Timedelta(hours=24)
            resumé = (
                df_total[df_total["Date_Heure"] >= cutoff24]
                .groupby("Ville")["Pluie (mm)"]
                .sum()
                .reset_index()
                .rename(columns={"Pluie (mm)": "Cumul 24h (mm)"})
                .sort_values("Cumul 24h (mm)", ascending=False)
            )
            resumé["Statut"] = resumé["Cumul 24h (mm)"].apply(
                lambda x: "🚨 ALERTE" if x >= SEUIL_ALERTE_MM
                else ("⚠️ Vigilance" if x >= SEUIL_VIGILANCE_MM else "✅ Normal")
            )
            st.dataframe(resumé, use_container_width=True, hide_index=True)

    # ========================================================
    # PAGE 2 – 📝 SAISIE RELEVÉ
    # ========================================================
    elif choix == "📝 Saisie Relevé":
        st.markdown(
            f'<div class="section-header">📝 Saisie – Station de {ville}</div>',
            unsafe_allow_html=True,
        )

        with st.form("form_saisie", clear_on_submit=True):
            c1, c2 = st.columns(2)
            d  = c1.date_input("📅 Date", value=date.today())
            h  = c1.selectbox("🕐 Heure d'observation", ["06:00", "08:00", "12:00", "18:00", "21:00", "Spécial"])
            h_spec = c1.text_input("Heure spéciale (HH:MM)", value="", disabled=(h != "Spécial"))

            p   = c2.number_input("🌧️ Pluie (mm)", min_value=0.0, max_value=999.9, step=0.1)
            tmp = c2.number_input("🌡️ Température (°C)", min_value=-5.0, max_value=55.0, step=0.1, value=28.0)
            hum = c2.number_input("💧 Humidité (%)", min_value=0, max_value=100, step=1, value=70)
            vent = c2.number_input("🌬️ Vent (km/h)", min_value=0.0, max_value=300.0, step=0.5, value=0.0)

            ph  = st.multiselect("⚡ Phénomènes observés", PHENOMENES_OPTIONS)
            obs = st.text_area("📝 Observations libres", placeholder="Notes complémentaires…")

            soumis = st.form_submit_button("💾 Enregistrer le relevé", use_container_width=True, type="primary")

        if soumis:
            heure_finale = h_spec if h == "Spécial" and h_spec else h
            # Validation minimale
            if h == "Spécial" and not h_spec:
                st.warning("⚠️ Veuillez renseigner l'heure spéciale.")
            else:
                path = f"Donnees_Villes/{ville}.csv"
                df_new = pd.DataFrame({
                    "Date_Heure":     [f"{d} {heure_finale}"],
                    "Pluie (mm)":     [p],
                    "Temperature (C)": [tmp],
                    "Humidite (%)":   [hum],
                    "Vent (km/h)":    [vent],
                    "Phenomenes":     [", ".join(ph) if ph else ""],
                    "Obs":            [obs],
                    "Saisi_par":      [st.session_state.username],
                })
                df_new.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
                charger_toutes_donnees.clear()
                st.success(f"✅ Relevé enregistré avec succès pour **{ville}** ({d} {heure_finale}) !")

                if p >= SEUIL_ALERTE_MM:
                    st.error(f"🚨 ALERTE ROUGE : précipitation de **{p} mm** détectée à {ville} !")
                elif p >= SEUIL_VIGILANCE_MM:
                    st.warning(f"⚠️ Vigilance : précipitation de **{p} mm** à {ville}.")

        # Aperçu des dernières saisies
        path_ville = f"Donnees_Villes/{ville}.csv"
        if os.path.exists(path_ville):
            st.markdown("##### 🕒 5 dernières saisies")
            preview = pd.read_csv(path_ville).tail(5).iloc[::-1]
            st.dataframe(preview, use_container_width=True, hide_index=True)

    # ========================================================
    # PAGE 3 – 📚 HISTORIQUE & CORRECTIONS
    # ========================================================
    elif choix == "📚 Historique & Corrections":
        st.markdown('<div class="section-header">📚 Historique & Gestion des Données</div>',
                    unsafe_allow_html=True)

        # Sélection de la station
        stations_dispo = sorted([f.replace(".csv", "") for f in os.listdir("Donnees_Villes") if f.endswith(".csv")])
        if role == "admin":
            v_sel = st.selectbox("🏙️ Station", stations_dispo if stations_dispo else [ville])
        else:
            v_sel = ville
            st.info(f"📍 Station : **{ville}**")

        path = f"Donnees_Villes/{v_sel}.csv"

        if os.path.exists(path):
            df_h = pd.read_csv(path)
            df_h["Date_Heure"] = pd.to_datetime(df_h["Date_Heure"], errors="coerce")

            # Filtres temporels
            fc1, fc2 = st.columns(2)
            if not df_h.empty and df_h["Date_Heure"].notna().any():
                min_date = df_h["Date_Heure"].min().date()
                max_date = df_h["Date_Heure"].max().date()
                date_debut = fc1.date_input("📅 Du", value=min_date, min_value=min_date, max_value=max_date)
                date_fin   = fc2.date_input("📅 Au", value=max_date, min_value=min_date, max_value=max_date)
                mask = (df_h["Date_Heure"].dt.date >= date_debut) & (df_h["Date_Heure"].dt.date <= date_fin)
                df_filtre = df_h[mask]
            else:
                df_filtre = df_h

            st.markdown(f"**{len(df_filtre)} enregistrement(s) trouvé(s)**")

            # Statistiques rapides
            if not df_filtre.empty and "Pluie (mm)" in df_filtre.columns:
                pluie_col = pd.to_numeric(df_filtre["Pluie (mm)"], errors="coerce").fillna(0)
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("🌧️ Cumul total", f"{pluie_col.sum():.1f} mm")
                s2.metric("📈 Max ponctuel", f"{pluie_col.max():.1f} mm")
                s3.metric("📉 Moy. par relevé", f"{pluie_col.mean():.1f} mm")
                s4.metric("📊 Nb relevés", len(df_filtre))

            if role == "admin":
                st.subheader("🛠️ Zone Admin – Édition des données")
                df_edite = st.data_editor(df_filtre, num_rows="dynamic", use_container_width=True)
                ca, cb, cc = st.columns(3)
                if ca.button("💾 Sauvegarder", type="primary"):
                    # Recomposer : lignes hors filtre + lignes éditées
                    if "mask" in dir():
                        df_reste = df_h[~mask]
                        df_final = pd.concat([df_reste, df_edite], ignore_index=True)
                    else:
                        df_final = df_edite
                    df_final.to_csv(path, index=False)
                    charger_toutes_donnees.clear()
                    st.success("✅ Données mises à jour !")
                    st.rerun()

                if cb.download_button(
                    "📥 Exporter Excel",
                    data=df_to_excel_bytes(df_filtre),
                    file_name=f"{v_sel}_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ):
                    pass

                if cc.button("🗑️ Vider la station", type="secondary"):
                    os.remove(path)
                    charger_toutes_donnees.clear()
                    st.warning("⚠️ Toutes les données de cette station ont été supprimées.")
                    st.rerun()
            else:
                st.dataframe(df_filtre, use_container_width=True, hide_index=True)
                st.download_button(
                    "📥 Télécharger mes données (CSV)",
                    data=df_filtre.to_csv(index=False).encode(),
                    file_name=f"{v_sel}_{date.today()}.csv",
                    mime="text/csv",
                )
        else:
            st.info("ℹ️ Aucun historique pour cette station.")

    # ========================================================
    # PAGE 4 – 📊 DASHBOARD ADMIN
    # ========================================================
    elif choix == "📊 Dashboard Admin":
        st.markdown('<div class="section-header">📊 Dashboard Administrateur</div>',
                    unsafe_allow_html=True)

        df_all = charger_toutes_donnees()

        # KPIs globaux
        if not df_all.empty:
            nb_stations  = df_all["Ville"].nunique()
            cumul_global = df_all["Pluie (mm)"].sum()
            cutoff24     = pd.Timestamp.now() - pd.Timedelta(hours=24)
            cumul_24h    = df_all[df_all["Date_Heure"] >= cutoff24]["Pluie (mm)"].sum()
            alertes      = df_all[df_all["Pluie (mm)"] >= SEUIL_ALERTE_MM]

            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f'<div class="kpi-card"><p>Stations actives</p><h3>{nb_stations}</h3></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="kpi-card vert"><p>Cumul global (mm)</p><h3>{cumul_global:.0f}</h3></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="kpi-card orange"><p>Cumul 24 h (mm)</p><h3>{cumul_24h:.1f}</h3></div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="kpi-card alerte"><p>Événements ≥ {SEUIL_ALERTE_MM} mm</p><h3>{len(alertes)}</h3></div>', unsafe_allow_html=True)

            st.divider()

            # Graphique cumul par station
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                cumul_villes = df_all.groupby("Ville")["Pluie (mm)"].sum().reset_index().sort_values("Pluie (mm)", ascending=False)
                fig_bar = px.bar(
                    cumul_villes, x="Ville", y="Pluie (mm)", color="Pluie (mm)",
                    color_continuous_scale="Blues",
                    title="☔ Cumul total par station",
                    labels={"Pluie (mm)": "mm"},
                )
                fig_bar.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_g2:
                # Répartition des phénomènes
                col_pheno = [c for c in df_all.columns if "phenom" in c.lower()]
                if col_pheno:
                    ph_series = df_all[col_pheno[0]].dropna().astype(str).str.split(", ").explode().str.strip()
                else:
                    ph_series = pd.Series(dtype='str')
                    ph_series = ph_series[ph_series.str.strip() != ""]
                if not ph_series.empty:
                    ph_count = ph_series.value_counts().reset_index()
                    ph_count.columns = ["Phénomène", "Nb"]
                    fig_pie = px.pie(ph_count, names="Phénomène", values="Nb",
                                     title="🌪️ Répartition des phénomènes",
                                     color_discrete_sequence=px.colors.qualitative.Set2)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("Aucun phénomène enregistré.")

            # Évolution temporelle globale
            df_daily = df_all.copy()
            df_daily["Jour"] = df_daily["Date_Heure"].dt.date
            df_daily_grp = df_daily.groupby(["Jour", "Ville"])["Pluie (mm)"].sum().reset_index()
            fig_line = px.line(
                df_daily_grp, x="Jour", y="Pluie (mm)", color="Ville",
                markers=True, title="📈 Évolution journalière des précipitations",
                line_shape="spline",
            )
            fig_line.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_line, use_container_width=True)

            # Alertes
            if not alertes.empty:
                st.warning(f"🚨 {len(alertes)} enregistrement(s) dépassant {SEUIL_ALERTE_MM} mm !")
                st.dataframe(
                    alertes[["Date_Heure", "Ville", "Pluie (mm)", "Phenomenes"]].sort_values("Pluie (mm)", ascending=False),
                    use_container_width=True, hide_index=True
                )

        else:
            st.info("ℹ️ Aucune donnée disponible.")

        st.divider()
        st.subheader("📤 Exportation & Envoi")
        col_e1, col_e2 = st.columns(2)

        # Téléchargement direct ZIP
        if col_e1.button("📦 Préparer l'archive ZIP", use_container_width=True):
            nom_zip = f"SODEXAM_{date.today()}.zip"
            with zipfile.ZipFile(nom_zip, "w") as z:
                for f in os.listdir("Donnees_Villes"):
                    z.write(os.path.join("Donnees_Villes", f), f)
            with open(nom_zip, "rb") as fz:
                col_e1.download_button(
                    "⬇️ Télécharger le ZIP",
                    data=fz.read(),
                    file_name=nom_zip,
                    mime="application/zip",
                )
            os.remove(nom_zip)

        with col_e2.form("form_email"):
            email_dest = st.text_input("📧 Destinataire", "direction@sodexam.ci")
            if st.form_submit_button("📨 Envoyer par e-mail", use_container_width=True):
                nom_zip = f"SODEXAM_{date.today()}.zip"
                with zipfile.ZipFile(nom_zip, "w") as z:
                    for f in os.listdir("Donnees_Villes"):
                        z.write(os.path.join("Donnees_Villes", f), f)
                if envoyer_email_archive(email_dest, nom_zip, str(date.today())):
                    st.success("✅ Email envoyé avec succès !")
                if os.path.exists(nom_zip):
                    os.remove(nom_zip)

    # ========================================================
    # PAGE 5 – 📈 ANALYSES GRAPHIQUES
    # ========================================================
    elif choix == "📈 Analyses Graphiques":
        st.markdown('<div class="section-header">📈 Analyses et Graphiques des Précipitations</div>',
                    unsafe_allow_html=True)

        df_t = charger_toutes_donnees()
        if df_t.empty:
            st.info("ℹ️ Aucune donnée disponible pour les graphiques.")
            st.stop()

        # Contrôles globaux
        all_villes = sorted(df_t["Ville"].unique())
        col_f1, col_f2, col_f3 = st.columns(3)
        v_plot = col_f1.multiselect("🏙️ Stations", all_villes, default=all_villes[:3])
        agg_mode = col_f2.selectbox("📅 Agrégation", ["Brut", "Journalière", "Hebdomadaire", "Mensuelle"])
        col_f3.markdown("<br>", unsafe_allow_html=True)  # spacer

        date_min = df_t["Date_Heure"].min().date()
        date_max = df_t["Date_Heure"].max().date()

        # ── Garde : min < max obligatoire pour st.slider ──────
        if date_min >= date_max:
            # Une seule journée de données → on utilise deux date_input
            st.info(
                f"📅 Une seule journée de données disponible : **{date_min}**. "
                "Ajoutez des relevés sur d'autres dates pour activer le filtre de période."
            )
            d_range = (date_min, date_max)
        else:
            d_range = st.slider(
                "🗓️ Période",
                min_value=date_min,
                max_value=date_max,
                value=(date_min, date_max),
            )

        if not v_plot:
            st.warning("⚠️ Sélectionnez au moins une station.")
            st.stop()

        df_p = df_t[
            (df_t["Ville"].isin(v_plot)) &
            (df_t["Date_Heure"].dt.date >= d_range[0]) &
            (df_t["Date_Heure"].dt.date <= d_range[1])
        ].copy()

        if df_p.empty:
            st.warning("Aucune donnée pour la sélection.")
            st.stop()

        # Agrégation
        if agg_mode != "Brut":
            freq_map = {"Journalière": "D", "Hebdomadaire": "W", "Mensuelle": "ME"}
            df_p = (
                df_p.set_index("Date_Heure")
                .groupby("Ville")["Pluie (mm)"]
                .resample(freq_map[agg_mode])
                .sum()
                .reset_index()
            )

        tabs = st.tabs(["📉 Évolution", "📊 Cumuls", "🕯️ Distribution", "📋 Tableau"])

        # Onglet 1 – Évolution temporelle
        with tabs[0]:
            fig_ev = px.line(
                df_p, x="Date_Heure", y="Pluie (mm)", color="Ville",
                markers=(agg_mode != "Brut"),
                title=f"Évolution des précipitations ({agg_mode})",
                line_shape="spline",
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            # Ligne seuil
            fig_ev.add_hline(y=SEUIL_ALERTE_MM, line_dash="dot",
                             line_color="red", annotation_text="Seuil alerte")
            fig_ev.add_hline(y=SEUIL_VIGILANCE_MM, line_dash="dash",
                             line_color="orange", annotation_text="Vigilance")
            fig_ev.update_layout(plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified")
            st.plotly_chart(fig_ev, use_container_width=True)

        # Onglet 2 – Cumuls
        with tabs[1]:
            cg1, cg2 = st.columns(2)
            cumul_total = df_p.groupby("Ville")["Pluie (mm)"].sum().reset_index()
            fig_bar = px.bar(
                cumul_total, x="Ville", y="Pluie (mm)", color="Ville",
                title="Cumul total par station",
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_bar.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white")
            cg1.plotly_chart(fig_bar, use_container_width=True)

            if agg_mode == "Mensuelle" or agg_mode == "Brut":
                df_mois = df_p.copy()
                df_mois["Mois"] = df_mois["Date_Heure"].dt.to_period("M").astype(str)
                cumul_mois = df_mois.groupby(["Mois", "Ville"])["Pluie (mm)"].sum().reset_index()
                fig_mbar = px.bar(
                    cumul_mois, x="Mois", y="Pluie (mm)", color="Ville",
                    barmode="group", title="Cumul mensuel par station",
                )
                fig_mbar.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                cg2.plotly_chart(fig_mbar, use_container_width=True)

        # Onglet 3 – Distribution
        with tabs[2]:
            fig_box = px.box(
                df_p, x="Ville", y="Pluie (mm)", color="Ville",
                points="outliers", title="Distribution des précipitations",
            )
            fig_box.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_box, use_container_width=True)

            fig_hist = px.histogram(
                df_p, x="Pluie (mm)", color="Ville",
                nbins=30, barmode="overlay", opacity=0.7,
                title="Histogramme des relevés",
            )
            fig_hist.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_hist, use_container_width=True)

        # Onglet 4 – Tableau
        with tabs[3]:
            st.dataframe(df_p, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Télécharger (CSV)",
                data=df_p.to_csv(index=False).encode(),
                file_name=f"analyse_{date.today()}.csv",
                mime="text/csv",
            )
            st.download_button(
                "📥 Télécharger (Excel)",
                data=df_to_excel_bytes(df_p),
                file_name=f"analyse_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # ========================================================
    # PAGE 6 – 🔴 RAPPORT PDF ALERTES
    # ========================================================
    elif choix == "🔴 Rapport PDF Alertes":
        st.markdown('<div class="section-header">🔴 Génération du Rapport PDF d\'Alertes</div>',
                    unsafe_allow_html=True)

        if not PDF_DISPONIBLE:
            st.error(
                "❌ Module `pdf_alertes.py` introuvable. "
                "Placez-le dans le même dossier que `sodexam_app.py`."
            )
            st.stop()

        df_all = charger_toutes_donnees()

        if df_all.empty:
            st.info("ℹ️ Aucune donnée disponible pour générer un rapport.")
            st.stop()

        # ── Panneau de configuration ──────────────────────────
        with st.container(border=True):
            st.markdown("#### ⚙️ Paramètres du rapport")
            pc1, pc2 = st.columns(2)

            date_min_g = df_all["Date_Heure"].min().date()
            date_max_g = df_all["Date_Heure"].max().date()
            # Garde : éviter date_max_g < date_min_g si une seule journée
            if date_min_g >= date_max_g:
                date_max_g = date_min_g + timedelta(days=1)

            debut_defaut = max(date_min_g, date_max_g - timedelta(days=30))
            pdf_date_debut = pc1.date_input(
                "📅 Période — Du",
                value=debut_defaut,
                min_value=date_min_g, max_value=date_max_g,
                key="pdf_deb",
            )
            pdf_date_fin = pc2.date_input(
                "📅 Période — Au",
                value=date_max_g,
                min_value=date_min_g, max_value=date_max_g,
                key="pdf_fin",
            )

            ps1, ps2 = st.columns(2)
            pdf_seuil = ps1.number_input(
                "🚨 Seuil d'alerte (mm)",
                min_value=1.0, max_value=500.0,
                value=float(SEUIL_ALERTE_MM), step=5.0,
            )
            pdf_titre = ps2.text_input(
                "📄 Titre du rapport",
                value=f"Rapport Alertes Pluviométriques – {date.today().strftime('%B %Y')}",
            )

            # Filtres optionnels
            all_villes_pdf = sorted(df_all["Ville"].unique())
            villes_pdf = st.multiselect(
                "📍 Filtrer par station(s) (vide = toutes)",
                all_villes_pdf,
                default=[],
                key="pdf_villes",
            )

            incl_vigilance = st.toggle(
                "⚠️ Inclure les événements de vigilance dans le tableau",
                value=True,
            )

        # ── Prévisualisation des alertes ──────────────────────
        df_pdf = df_all.copy()
        if villes_pdf:
            df_pdf = df_pdf[df_pdf["Ville"].isin(villes_pdf)]
        df_pdf = df_pdf[
            (df_pdf["Date_Heure"].dt.date >= pdf_date_debut) &
            (df_pdf["Date_Heure"].dt.date <= pdf_date_fin)
        ]

        df_alertes_prev  = df_pdf[df_pdf["Pluie (mm)"] >= pdf_seuil]
        df_vigil_prev    = df_pdf[
            (df_pdf["Pluie (mm)"] >= SEUIL_VIGILANCE_MM) &
            (df_pdf["Pluie (mm)"] < pdf_seuil)
        ]

        # KPI prévisualisation
        pv1, pv2, pv3, pv4 = st.columns(4)
        pv1.metric("🚨 Alertes détectées",  len(df_alertes_prev))
        pv2.metric("⚠️ Vigilances",          len(df_vigil_prev))
        pv3.metric("📍 Stations concernées",
                   df_alertes_prev["Ville"].nunique() if not df_alertes_prev.empty else 0)
        pv4.metric("💧 Max ponctuel",
                   f"{df_pdf['Pluie (mm)'].max():.1f} mm" if not df_pdf.empty else "—")

        if not df_alertes_prev.empty:
            st.markdown("##### 📋 Aperçu des alertes qui seront dans le PDF")
            st.dataframe(
                df_alertes_prev[["Date_Heure", "Ville", "Pluie (mm)", "Phenomenes"]]
                .sort_values("Pluie (mm)", ascending=False)
                .head(10),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("ℹ️ Aucune alerte sur la période sélectionnée. Le rapport contiendra une mention 'RAS'.")

        st.divider()

        # ── Bouton de génération ──────────────────────────────
        col_gen, col_email_pdf = st.columns([1, 1])

        with col_gen:
            st.markdown("##### 📥 Téléchargement direct")
            if st.button("🔄 Générer le PDF", type="primary", use_container_width=True, key="btn_gen_pdf"):
                with st.spinner("⏳ Génération du rapport en cours…"):
                    try:
                        logo_p = next(
                            (p for p in ["logo.png","logo.jpg","LOGO.PNG"] if os.path.exists(p)),
                            None
                        )
                        pdf_bytes = generer_rapport_alertes_pdf(
                            df_total=df_pdf if villes_pdf else df_all[
                                (df_all["Date_Heure"].dt.date >= pdf_date_debut) &
                                (df_all["Date_Heure"].dt.date <= pdf_date_fin)
                            ],
                            seuil_mm=pdf_seuil,
                            date_debut=pdf_date_debut,
                            date_fin=pdf_date_fin,
                            titre_rapport=pdf_titre,
                            generateur=st.session_state.username,
                            logo_path=logo_p,
                        )
                        st.session_state["pdf_cache"]       = pdf_bytes
                        st.session_state["pdf_nom_fichier"] = (
                            f"SODEXAM_Alertes_{pdf_date_debut.strftime('%Y%m%d')}_"
                            f"{pdf_date_fin.strftime('%Y%m%d')}.pdf"
                        )
                        st.success(f"✅ PDF prêt — {len(pdf_bytes)/1024:.0f} Ko")
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la génération : {e}")

            if "pdf_cache" in st.session_state:
                st.download_button(
                    label="⬇️ Télécharger le PDF",
                    data=st.session_state["pdf_cache"],
                    file_name=st.session_state["pdf_nom_fichier"],
                    mime="application/pdf",
                    use_container_width=True,
                )

        with col_email_pdf:
            st.markdown("##### 📨 Envoi par e-mail")
            with st.form("form_pdf_email"):
                dest_pdf = st.text_input("Destinataire", "direction@sodexam.ci")
                note_pdf = st.text_area(
                    "Message accompagnateur (optionnel)",
                    value="Veuillez trouver ci-joint le rapport d'alertes pluviométriques.",
                    height=80,
                )
                envoi_pdf = st.form_submit_button(
                    "📨 Générer & Envoyer", use_container_width=True
                )
            if envoi_pdf:
                with st.spinner("Génération + envoi en cours…"):
                    try:
                        logo_p = next(
                            (p for p in ["logo.png","logo.jpg","LOGO.PNG"] if os.path.exists(p)),
                            None
                        )
                        df_envoi = df_all[
                            (df_all["Date_Heure"].dt.date >= pdf_date_debut) &
                            (df_all["Date_Heure"].dt.date <= pdf_date_fin)
                        ]
                        if villes_pdf:
                            df_envoi = df_envoi[df_envoi["Ville"].isin(villes_pdf)]
                        pdf_bytes_mail = generer_rapport_alertes_pdf(
                            df_total=df_envoi,
                            seuil_mm=pdf_seuil,
                            date_debut=pdf_date_debut,
                            date_fin=pdf_date_fin,
                            titre_rapport=pdf_titre,
                            generateur=st.session_state.username,
                            logo_path=logo_p,
                        )
                        nom_pdf_tmp = f"/tmp/SODEXAM_{date.today()}.pdf"
                        with open(nom_pdf_tmp, "wb") as fout:
                            fout.write(pdf_bytes_mail)
                        _envoyer_pdf_email(dest_pdf, nom_pdf_tmp, pdf_titre, note_pdf)
                        os.remove(nom_pdf_tmp)
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")

        # ── Guide d'utilisation ───────────────────────────────
        with st.expander("ℹ️ Contenu du rapport PDF"):
            st.markdown("""
| Section | Contenu |
|---|---|
| **En-tête** | Logo SODEXAM, titre, pied de page numéroté |
| **KPIs** | Nb alertes · Nb vigilances · Stations touchées · Max ponctuel |
| **Tableau alertes** | Date, Station, mm, Niveau (🚨/⚠️), Phénomènes, Agent |
| **Graphique 1** | Barres horizontales : cumul par station (rouge = alerte) |
| **Graphique 2** | Courbe temporelle multi-stations + lignes de seuils |
| **Graphique 3** | Camembert des phénomènes observés |
| **Graphique 4** | Scatter intensité max vs moyenne (taille = nb relevés) |
| **Note méthodo** | Définition des seuils, sources des données |
            """)

    # ========================================================
    # PAGE 7 – ⚙️ GESTION DES COMPTES (admin)
    # ========================================================
    elif choix == "⚙️ Gestion des Comptes":
        st.markdown('<div class="section-header">⚙️ Gestion des Utilisateurs</div>',
                    unsafe_allow_html=True)

        u_df = charger_utilisateurs()

        # Tableau interactif des comptes
        st.subheader("👥 Comptes existants")
        for i, r in u_df.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.write(f"👤 **{r['identifiant']}**")
            col2.write(f"📍 {r['ville']}")
            col3.write(f"🏷️ {r.get('role','agent').upper()}")
            if r["identifiant"] != "admin":
                if col4.button("🗑️", key=f"del_{i}", help="Supprimer ce compte"):
                    u_df = u_df.drop(i).reset_index(drop=True)
                    u_df.to_csv("utilisateurs.csv", index=False)
                    charger_utilisateurs.clear()
                    st.success("Compte supprimé.")
                    st.rerun()

        st.divider()
        st.subheader("➕ Ajouter / Modifier un compte")
        with st.form("form_add_user"):
            fc1, fc2 = st.columns(2)
            ni  = fc1.text_input("Identifiant")
            np  = fc1.text_input("Mot de passe", type="password")
            nv  = fc2.selectbox("Station", sorted(COORDS_STATIONS.keys()))
            nr  = fc2.selectbox("Rôle", ["agent", "superviseur", "admin"])
            ne  = st.text_input("Email (optionnel)")
            if st.form_submit_button("💾 Enregistrer le compte", type="primary"):
                if ni and np:
                    new_row = pd.DataFrame({
                        "identifiant":  [ni],
                        "mot_de_passe": [hash_password(np)],
                        "ville":        [nv],
                        "role":         [nr],
                        "email":        [ne],
                    })
                    u_df = pd.concat([u_df[u_df["identifiant"] != ni], new_row], ignore_index=True)
                    u_df.to_csv("utilisateurs.csv", index=False)
                    charger_utilisateurs.clear()
                    st.success(f"✅ Compte **{ni}** enregistré !")
                    st.rerun()
                else:
                    st.warning("Identifiant et mot de passe obligatoires.")
