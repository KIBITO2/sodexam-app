# === CONTENU DU FICHIER pdf_alertes.py ===
from fpdf import FPDF
from datetime import datetime

class SODEXAM_PDF(FPDF):
    def header(self):
        self.set_fill_color(0, 63, 138) # Bleu SODEXAM
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("Arial", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "SODEXAM - RAPPORT D'ALERTE", ln=True, align="C")
        self.ln(10)

def generer_rapport_alertes_pdf(df_alertes, seuil):
    pdf = SODEXAM_PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 10, f"Alertes detectees au-dessus de {seuil} mm", ln=True)
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    for _, row in df_alertes.iterrows():
        texte = f"- {row['Date_Heure']} | {row['Ville']} : {row['Pluie (mm)']} mm ({row.get('Phenomenes', 'RAS')})"
        pdf.multi_cell(0, 10, texte)
    
    filename = "alerte_sodexam.pdf"
    pdf.output(filename)
    return filename
