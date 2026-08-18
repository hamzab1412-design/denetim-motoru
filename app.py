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
st.set_page_config(layout="wide", page_title="Master Denetim Motoru - Komple Sistem")

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
        "min_beton": "C30", "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği esastır."
    },
    "Adana Büyükşehir Belediyesi": {
        "min_beton": "C35", "ozel_sartlar": "Adana Büyükşehir İmar Yönetmeliği kuralları geçerlidir."
    },
    "Adana - Çukurova Belediyesi": {
        "min_beton": "C35", "ozel_sartlar": "Çukurova 1/1000 İmar Planı Notları zorunludur."
    }
}

# --- 3. YARDIMCI VE MÜHENDİSLİK FONKSİYONLARI ---
def check_merdiven_ve_tarama(doc):
    try:
        msp = doc.modelspace()
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs', 'merdiven-basamak']])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
        return basamak, tarama
    except: return 0, 0

def analyze_dxf_structure(doc):
    try:
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
st.subheader("📁 Proje ve Rapor Yükleme Paneli")
col1, col2 = st.columns(2)

with col1:
    mimari_dxf_file = st.file_uploader("Mimari Proje (DXF)", type=["dxf"], key="mimari")
with col2:
    statik_dxf_file = st.file_uploader("Statik Proje (DXF)", type=["dxf"], key="statik")

if "png_path" not in st.session_state: st.session_state.png_path = None
if "master_report" not in st.session_state: st.session_state.master_report = None

# --- İSTEDİĞİN GÖRSELLEŞTİRME VE DENETİM AKIŞI ---
if mimari_dxf_file:
    try:
        # Geçici kaydet ve ezdxf ile aç
        temp_dxf_path = "temp_aktif_m.dxf"
        with open(temp_dxf_path, "wb") as f: f.write(mimari_dxf_file.getvalue())
        doc = ezdxf.readfile(temp_dxf_path)
        
        # 1. Adım: Projeyi Görselleştirme Butonu
        if st.button("🖼️ 1. DXF Dosyasını Görselleştir"):
            try:
                progress_bar = st.progress(0, text="DXF dosyası işleniyor...")
                
                progress_bar.progress(50, text="%50 - Vektörler ve katmanlar çiziliyor...")
                fig = plt.figure(figsize=(10, 10))
                ax = fig.add_axes([0, 0, 1, 1])
                Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
                
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

        # 2. Adım: OpenAI ile Proje Denetimini Başlat
        if st.button("🤖 2. OpenAI ile Proje Denetimini Başlat"):
            if st.session_state.get('png_path'):
                with st.spinner("🔄 Mühendislik kuralları taranıyor ve rapor hazırlanıyor..."):
                    basamak, tarama = check_merdiven_ve_tarama(doc)
                    texts = analyze_dxf_structure(doc)
                    
                    st.subheader("🛠️ Otomatik Geometrik ve Mühendislik Bulguları")
                    c1, c2 = st.columns(2)
                    c1.metric("Merdiven Basamak Sayısı", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA (<17)")
                    c2.metric("Kolon Taraması (Hatch)", "Tespit Edildi" if tarama > 0 else "Eksik")

                    system_prompt = f"Sen kıdemli bir İnşaat Mühendisi ve İmar Baş Kontrolörüsün. Seçilen İdare: {secilen_belediye_profil}"
                    user_prompt = f"DXF içinden okunan metinler ve bulgular doğrultusunda eksiklik raporu hazırla. Merdiven: {basamak}, Kolon Taraması: {tarama}"
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                        max_tokens=2000
                    )
                    st.session_state.master_report = response.choices[0].message.content
                    st.success("✅ Proje denetimi tamamlandı!")
            else:
                st.warning("⚠️ Lütfen önce 1. Adım ile DXF dosyasını görselleştirin.")

    except Exception as e:
        st.error(f"DXF dosyası okunamadı: {e}")

# --- RAPOR GÖSTERİMİ ---
if st.session_state.master_report:
    st.markdown("---")
    st.header("📑 Resmi Mühendislik İnceleme Tutanağı")
    st.markdown(st.session_state.master_report)
    st.download_button(
        label="📥 Tutanağı İndir (.md)",
        data=st.session_state.master_report,
        file_name="Muhendislik_Inceleme_Tutanagi.md",
        mime="text/markdown",
        use_container_width=True
    )