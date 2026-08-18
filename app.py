import streamlit as st
import ezdxf
import json
import base64
import io
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from openai import OpenAI
from pypdf import PdfReader

# Sayfa Ayarları
st.set_page_config(layout="wide", page_title="Master Denetim Motoru (Gelişmiş Mühendislik Analizi)")

# --- 1. ŞİFRE KORUMASI ---
def check_password():
    if "password_correct" not in st.session_state: st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔐 MRB Mimarlık - Denetim Motoru Giriş")
        password = st.text_input("Şifreyi Giriniz:", type="password")
        if st.button("Giriş Yap"):
            if password == "MRB_Mimarlık_123":
                st.session_state.password_correct = True
                st.rerun()
            else: st.error("❌ Hatalı Şifre!")
        return False
    return True

if not check_password(): st.stop()

# --- 2. MÜHENDİSLİK VE YARDIMCI FONKSİYONLAR ---
def check_merdiven_ve_tarama(dxf_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs']])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
        return basamak, tarama
    except: return 0, 0

def compare_dxf_layers(mimari_path, statik_path):
    try:
        doc_m = ezdxf.readfile(mimari_path)
        doc_s = ezdxf.readfile(statik_path)
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_axes([0, 0, 1, 1])
        Frontend(RenderContext(doc_m), MatplotlibBackend(ax, color_mode='mono', style={'color': 'blue'})).draw_layout(doc_m.modelspace())
        Frontend(RenderContext(doc_s), MatplotlibBackend(ax, color_mode='mono', style={'color': 'red'})).draw_layout(doc_s.modelspace())
        img_path = "comparison.png"
        plt.savefig(img_path, dpi=150)
        plt.close(fig)
        return img_path
    except: return None

def read_pdf_text(uploaded_file):
    try:
        pdf_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted: text += extracted + "\n"
        return text if text.strip() else "PDF metin çıkarılamadı."
    except: return "PDF okuma hatası"

def analyze_dxf_structure(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        texts = [e.dxf.text.strip() for e in doc.modelspace().query('TEXT MTEXT') if e.dxf.text.strip()]
        return texts
    except: return []

# --- 3. VERİTABANI VE API ---
BELEDIYE_VERITABANI = {
    "Bakanlık Standartları": {"min_beton": "C30", "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği"},
    "Adana Büyükşehir Belediyesi": {"min_beton": "C35", "ozel_sartlar": "Adana İmar Yönetmeliği"}
}

with st.sidebar:
    user_api_key = st.text_input("OpenAI API Anahtarınız:", type="password")
if not user_api_key: st.stop()
client = OpenAI(api_key=user_api_key)

# --- 4. ARAYÜZ ---
st.title("🏛️ Master Yapı Denetim Uzman Mühendislik Modülü")
secilen_belediye_profil = st.selectbox("Denetimin tabi olacağı belediye:", list(BELEDIYE_VERITABANI.keys()))

col1, col2 = st.columns(2)
with col1:
    mimari_dxf = st.file_uploader("Mimari Proje (DXF)", type=["dxf"])
    idari_evrak = st.file_uploader("İdari Evrak (PDF)", type=["pdf"])
with col2:
    statik_dxf = st.file_uploader("Statik Proje (DXF)", type=["dxf"])
    statik_rapor = st.file_uploader("Statik Hesap Raporu (PDF)", type=["pdf"])

if st.button("🏗️ Kapsamlı Mühendislik Analizini Başlat"):
    if mimari_dxf and statik_dxf:
        with open("temp_m.dxf", "wb") as f: f.write(mimari_dxf.getvalue())
        with open("temp_s.dxf", "wb") as f: f.write(statik_dxf.getvalue())
        
        # Analizler
        basamak, tarama = check_merdiven_ve_tarama("temp_m.dxf")
        
        st.subheader("🛠️ Otomatik Mühendislik Bulguları")
        c1, c2 = st.columns(2)
        c1.metric("Merdiven Basamak", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA")
        c2.metric("Kolon Taraması", "Tespit Edildi" if tarama > 0 else "Eksik")
        
        st.subheader("🔍 Mimari-Statik Çakıştırma Analizi")
        st.image(compare_dxf_layers("temp_m.dxf", "temp_s.dxf"), caption="Mavi: Mimari, Kırmızı: Statik")
        
        st.success("Mühendislik ve geometri analizleri tamamlandı.")
    else:
        st.warning("Lütfen mimari ve statik dosyaları yükleyin.")