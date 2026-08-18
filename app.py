import streamlit as st
import ezdxf
import json
import base64
import io
import time
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from openai import OpenAI
from pypdf import PdfReader

# Sayfa Ayarları
st.set_page_config(layout="wide", page_title="Master Denetim Motoru")

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

# --- 2. BELEDİYE VERİTABANI ---
BELEDIYE_VERITABANI = {
    "Bakanlık Standartları (Genel PAİY & TBDY 2018) [Varsayılan]": {
        "asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30",
        "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği tam metni ve ulusal teknik yönetmelikler esastır."
    },
    "Adana Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Adana Büyükşehir İmar Yönetmeliği geçerlidir."},
    "Adana - Çukurova Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Çukurova 1/1000 İmar Planı Notları zorunludur."}
}

# --- 3. YARDIMCI FONKSİYONLAR ---
def read_pdf_text(uploaded_file):
    try:
        pdf_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted: text += extracted + "\n"
        return text if text.strip() else "PDF metin çıkarılamadı."
    except Exception as e: return f"PDF okuma hatası: {e}"

def analyze_dxf_structure(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        texts = [e.dxf.text.strip() for e in doc.modelspace().query('TEXT MTEXT') if e.dxf.text.strip()]
        return texts
    except: return []

# --- 4. API VE SIDEBAR ---
with st.sidebar:
    st.subheader("🔑 Kullanıcı API Ayarları")
    user_api_key = st.text_input("OpenAI API Anahtarınız:", type="password")
if not user_api_key: st.stop()
client = OpenAI(api_key=user_api_key)

# --- 5. ANA ARAYÜZ ---
st.title("🏛️ Belediye İmar ve Plan-Proje İnceleme Bürosu")
secilen_belediye_profil = st.selectbox("Denetimin tabi olacağı belediye veya yasal idare:", list(BELEDIYE_VERITABANI.keys()))
aktif_sartlar = BELEDIYE_VERITABANI[secilen_belediye_profil]
st.success(f"📌 **Aktif Mevzuat Şartları:** {aktif_sartlar['ozel_sartlar']} (Min. Beton: {aktif_sartlar['min_beton']})")

st.markdown("---")
st.subheader("📁 Ruhsat, Proje, Hesap Raporu ve İdari Evrak Yükleme Paneli")
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🏛️ Mimari & İdari Projeler")
    mimari_dxf = st.file_uploader("Mimari Proje (DXF)", type=["dxf"], key="mimari")
    idari_evraklar = st.file_uploader("İmar Durumu / Aplikasyon / Plankote (PDF)", type=["pdf"], key="idari")

with col2:
    st.markdown("### 🧱 Statik & Yasal Projeler")
    statik_dxf = st.file_uploader("Statik Proje (DXF)", type=["dxf"], key="statik")
    statik_rapor = st.file_uploader("Statik Hesap Raporu (PDF)", type=["pdf", "txt"], key="rapor")

if "png_path" not in st.session_state: st.session_state.png_path = None
if "master_report" not in st.session_state: st.session_state.master_report = None

# --- 6. 12 AĞUSTOS'TAKİ SORUNSUZ GÖRSELLEŞTİRME VE AKIŞ ---
if mimari_dxf:
    try:
        temp_dxf_path = "temp_aktif_m.dxf"
        with open(temp_dxf_path, "wb") as f: f.write(mimari_dxf.getvalue())
        doc = ezdxf.readfile(temp_dxf_path)
        
        # 1. Adım: Projeyi Görselleştirme (Orijinal Haliyle)
        if st.button("🖼️ 1. DXF Dosyasını Görselleştir"):
            try:
                progress_bar = st.progress(0, text="DXF dosyası işleniyor...")
                progress_bar.progress(50, text="%50 - Vektörler ve katmanlar çiziliyor...")
                
                fig = plt.figure(figsize=(12, 12))
                ax = fig.add_axes([0, 0, 1, 1])
                Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace())
                
                png_path = "temp_dxf_render.png"
                fig.savefig(png_path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                
                progress_bar.progress(100, text="%100 - Tamamlandı!")
                time.sleep(0.3)
                progress_bar.empty()
                
                st.session_state['png_path'] = png_path
                st.image(png_path, caption="Yüklenen DXF Projesinin Vektörel Görseli")
                st.success("✅ Proje başarıyla görselleştirildi ve OpenAI incelemesine hazır!")
            except Exception as e: 
                st.error(f"Render hatası: {e}")

        st.markdown("---")

        # 2. Adım: OpenAI (GPT-4o) ile Proje Denetimini Başlat
        if st.button("🤖 2. OpenAI ile Proje Denetimini Başlat"):
            if st.session_state.get('png_path'):
                with st.spinner("🔄 Proje görseli ve verileri OpenAI (GPT-4o) ile inceleniyor..."):
                    
                    pdf_metni = read_pdf_text(statik_rapor) if statik_rapor else ""
                    idari_metin = read_pdf_text(idari_evraklar) if idari_evraklar else ""
                    texts = analyze_dxf_structure(temp_dxf_path)
                    
                    with open(st.session_state['png_path'], "rb") as img_file:
                        encoded_image = base64.b64encode(img_file.read()).decode('utf-8')

                    system_prompt = f"Sen kıdemli bir İnşaat Mühendisi ve İmar Baş Kontrolörüsün. Seçilen İdare: {secilen_belediye_profil}"
                    user_prompt = [
                        {"type": "text", "text": f"Lütfen bu mimari projenin çizim görselini ve verilerini (Statik Rapor: {pdf_metni[:2000]}) incele. Yapı denetim ve imar yönetmeliği açısından eksiklik raporu hazırla."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                    ]
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=2000
                    )
                    st.session_state.master_report = response.choices[0].message.content
                    st.success("✅ Proje denetimi tamamlandı!")
            else:
                st.warning("⚠️ Lütfen önce 1. Adım ile DXF dosyasını görselleştirin.")

    except Exception as e:
        st.error(f"Dosya okuma hatası: {e}")

# --- 7. RAPOR GÖSTERİMİ ---
if st.session_state.master_report:
    st.markdown("---")
    st.header("📑 Resmi Mühendislik İnceleme Tutanağı")
    st.markdown(st.session_state.master_report)
    st.download_button(
        label="📥 Tutanağı İndir (.md)",
        data=st.session_state.master_report,
        file_name="Inceleme_Tutanagi.md",
        mime="text/markdown",
        use_container_width=True
    )