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
st.set_page_config(layout="wide", page_title="Master Denetim Motoru - Tam Donanımlı Sistem")

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

# --- 2. BELEDİYE VERİTABANI & SÖZLÜK ---
BELEDIYE_VERITABANI = {
    "Bakanlık Standartları (Genel PAİY & TBDY 2018) [Varsayılan]": {
        "asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30",
        "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği tam metni ve ulusal teknik yönetmelikler esastır."
    },
    "Adana Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Adana Büyükşehir İmar Yönetmeliği, ana arter nizamı ve toplu ulaşım entegrasyon kuralları geçerlidir."},
    "Adana - Çukurova Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Çukurova 1/1000 İmar Planı Notları, yerel zemin koşulları ve Deprem Bölgeleri Yönetmeliği zorunludur."},
    "İstanbul Büyükşehir Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "İBB İmar Yönetmeliği, boğaziçi öngörünüm kuralları ve akustik rapor zorunluluğu vardır."},
    "Balıkesir Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Balıkesir Büyükşehir İmar Yönetmeliği, kırsal kalkınma ve turizm bölgesi yapılaşma esasları geçerlidir."}
}

# --- 3. YARDIMCI VE MÜHENDİSLİK FONKSİYONLARI ---
def read_pdf_text(uploaded_file):
    try:
        pdf_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted: text += extracted + "\n"
        return text if text.strip() else "PDF dosyasından metin çıkarılamadı."
    except Exception as e: return f"PDF okuma hatası: {e}"

def check_merdiven_ve_tarama(dxf_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs', 'merdiven-basamak']])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
        return basamak, tarama
    except: return 0, 0

def dxf_to_image(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp, finalize=True)
        img_path = "temp_dxf_render.png"
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        with open(img_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception: return None

def compare_dxf_layers(mimari_path, statik_path):
    try:
        doc_m = ezdxf.readfile(mimari_path)
        doc_s = ezdxf.readfile(statik_path)
        fig, ax = plt.subplots(figsize=(10, 10))
        Frontend(RenderContext(doc_m), MatplotlibBackend(ax), color_mode='mono', style={'color': 'blue'}).draw_layout(doc_m.modelspace(), finalize=True)
        Frontend(RenderContext(doc_s), MatplotlibBackend(ax), color_mode='mono', style={'color': 'red'}).draw_layout(doc_s.modelspace(), finalize=True)
        img_path = "comparison.png"
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return img_path
    except Exception: return None

def analyze_dxf_structure(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        layers = [layer.dxf.name.lower() for layer in doc.layers]
        texts = [e.dxf.text.strip() for e in doc.modelspace().query('TEXT MTEXT') if e.dxf.text.strip()]
        return layers, texts
    except Exception: return [], []

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
    idari_evraklar = st.file_uploader("İmar Durumu / Aplikasyon / Plankote (PDF/Görsel)", type=["pdf", "png", "jpg"], key="idari")

with col2:
    st.markdown("### 🧱 Statik & Yasal Projeler")
    statik_dxf = st.file_uploader("Statik Proje (DXF)", type=["dxf"], key="statik")
    statik_rapor = st.file_uploader("Statik Hesap Raporu (PDF)", type=["pdf", "txt"], key="rapor")

if "audit_data" not in st.session_state: st.session_state.audit_data = None
if "master_report" not in st.session_state: st.session_state.master_report = None
if "show_interactive_form" not in st.session_state: st.session_state.show_interactive_form = False

# --- 6. ÇALIŞTIRMA BUTONU VE YÜKLEME EKRANI ---
if st.button("🏛️ Kapsamlı Mühendislik ve Kot/Aks Denetimini Başlat"):
    if mimari_dxf or statik_dxf or statik_rapor or idari_evraklar:
        # Eski havalı yükleme ekranı (Spinner) aktif!
        with st.spinner(f"🔄 '{secilen_belediye_profil}' şartlarıyla kot, aks, merdiven ve çakıştırma analizleri yükleniyor..."):
            
            if mimari_dxf:
                with open("temp_m.dxf", "wb") as f: f.write(mimari_dxf.getvalue())
            if statik_dxf:
                with open("temp_s.dxf", "wb") as f: f.write(statik_dxf.getvalue())
            
            # Otomatik Mühendislik Bulguları
            if mimari_dxf:
                basamak, tarama = check_merdiven_ve_tarama("temp_m.dxf")
                st.subheader("🛠️ Otomatik Geometrik ve Mühendislik Bulguları")
                c1, c2 = st.columns(2)
                c1.metric("Merdiven Basamak Sayısı", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA (<17)")
                c2.metric("Kolon Taraması (Hatch)", "Tespit Edildi" if tarama > 0 else "Eksik")

            # Görselleştirme Özelliği (Çakıştırma)
            if mimari_dxf and statik_dxf:
                st.subheader("🔍 Mimari (Mavi) - Statik (Kırmızı) Çakıştırma Görselleştirmesi")
                comp_img = compare_dxf_layers("temp_m.dxf", "temp_s.dxf")
                if comp_img:
                    st.image(comp_img, caption="Mavi: Mimari Proje, Kırmızı: Statik Proje", use_container_width=True)
                else:
                    st.warning("Çizim motoru görselleştirmeyi tamamlayamadı, metinsel denetim yürütülüyor.")

            # AI Raporlama Hazırlığı
            m_texts = analyze_dxf_structure("temp_m.dxf")[1] if mimari_dxf else []
            s_texts = analyze_dxf_structure("temp_s.dxf")[1] if statik_dxf else []
            
            system_prompt = f"Sen kıdemli bir İnşaat Mühendisi ve Belediye İmar Baş Kontrolörüsün. Seçilen İdare: {secilen_belediye_profil}"
            user_prompt = "Projeleri incele ve resmi yapı denetim raporu formatında eksiklikleri çıkar."
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    max_tokens=2000
                )
                st.session_state.master_report = response.choices[0].message.content
                st.success("Mühendislik denetim ve görselleştirme analizi başarıyla tamamlandı!")
            except Exception as e:
                st.error(f"AI Analiz Hatası: {e}")
    else:
        st.warning("Lütfen denetimi başlatmak için en azından bir proje dosyası yükleyin.")

# --- 7. RAPOR GÖSTERİMİ ---
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