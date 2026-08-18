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
        "asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30",
        "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği tam metni ve ulusal teknik yönetmelikler esastır."
    },
    "Adana Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Adana Büyükşehir İmar Yönetmeliği, ana arter nizamı ve toplu ulaşım kuralları geçerlidir."},
    "Adana - Çukurova Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Çukurova 1/1000 İmar Planı Notları ve Deprem Yönetmeliği zorunludur."},
    "İstanbul Büyükşehir Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "İBB İmar Yönetmeliği ve akustik rapor zorunluluğu vardır."},
    "Balıkesir Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Balıkesir Büyükşehir İmar Yönetmeliği, kırsal kalkınma esasları geçerlidir."}
}

# --- 3. MÜHENDİSLİK VE YARDIMCI FONKSİYONLAR ---
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

def check_merdiven_ve_tarama(dxf_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs', 'merdiven-basamak']])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
        return basamak, tarama
    except: return 0, 0

def analyze_engineering_details(dxf_path, pdf_text):
    try:
        doc = ezdxf.readfile(dxf_path)
        texts = [e.dxf.text.strip().lower() for e in doc.modelspace().query('TEXT MTEXT') if e.dxf.text.strip()]
        combined_text = " ".join(texts) + " " + pdf_text.lower()
        
        return {
            "Paspayı Detayı": any(k in combined_text for k in ("paspayı", "cover", "2.5cm", "3cm")),
            "Etriye Sıklaştırma": any(k in combined_text for k in ("etriye", "sıklaştırma", "düğüm")),
            "Beton Sınıfı Yazımı": any(k in combined_text for k in ("c30", "c35", "c40")),
            "Temel Altı Drenaj": any(k in combined_text for k in ("drenaj", "yalıtım", "su yalıtımı")),
            "Zemin Etüdü Uyumu": any(k in combined_text for k in ("zemin", "etüt", "sondaj"))
        }
    except:
        return {"Paspayı Detayı": False, "Etriye Sıklaştırma": False, "Beton Sınıfı Yazımı": False, "Temel Altı Drenaj": False, "Zemin Etüdü Uyumu": False}

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
st.title("🏛️ Belediye İmar ve Plan-Proje İnceleme Bürosu - Master Denetim Masası")
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
if "audit_data" not in st.session_state: st.session_state.audit_data = None
if "master_report" not in st.session_state: st.session_state.master_report = None
if "show_interactive_form" not in st.session_state: st.session_state.show_interactive_form = False

# --- 6. ADIM 1: ORİJİNAL SORUNSUZ GÖRSELLEŞTİRME ---
if mimari_dxf:
    try:
        temp_dxf_path = "temp_aktif_m.dxf"
        with open(temp_dxf_path, "wb") as f: f.write(mimari_dxf.getvalue())
        doc = ezdxf.readfile(temp_dxf_path)
        
        if st.button("🖼️ 1. DXF Dosyasını Görselleştir"):
            try:
                progress_bar = st.progress(0, text="DXF dosyası işleniyor...")
                progress_bar.progress(50, text="%50 - Vektörler ve katmanlar çiziliyor...")
                
                fig = plt.figure(figsize=(12, 12))
                ax = fig.add_axes([0, 0, 1, 1])
                # Orijinal, hiçbir hata vermeyen sade ve sağlam çizim yöntemi
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

        # --- 7. ADIM 2: OPENAI VE MÜHENDİSLİK DENETİMİ ---
        if st.button("🤖 2. OpenAI ile Kapsamlı Mühendislik Denetimini Başlat"):
            if st.session_state.get('png_path'):
                with st.spinner("🔄 Mühendislik kuralları, raporlar ve görsel OpenAI (GPT-4o) ile inceleniyor..."):
                    
                    pdf_metni = read_pdf_text(statik_rapor) if statik_rapor else ""
                    idari_metin = read_pdf_text(idari_evraklar) if idari_evraklar else ""
                    basamak, tarama = check_merdiven_ve_tarama(temp_dxf_path)
                    eng_details = analyze_engineering_details(temp_dxf_path, pdf_metni)
                    
                    st.subheader("🛠️ Otomatik Mühendislik & Geometri Bulguları")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Merdiven Basamak", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA (<17)")
                    c2.metric("Kolon Taraması", "Tam" if tarama > 0 else "Eksik")
                    c3.metric("Beton Sınıfı Notu", "Tespit Edildi" if eng_details["Beton Sınıfı Yazımı"] else "Eksik")
                    c4.metric("Paspayı Detayı", "Var" if eng_details["Paspayı Detayı"] else "Yok")

                    with open(st.session_state['png_path'], "rb") as img_file:
                        encoded_image = base64.b64encode(img_file.read()).decode('utf-8')

                    system_prompt = f"""
                    Sen kıdemli bir İnşaat Mühendisi ve Belediye İmar Baş Kontrolörüsün.
                    Seçilen İdare: {secilen_belediye_profil}
                    Belediye Şartları: {aktif_sartlar['ozel_sartlar']}
                    Min. Beton Sınırı: {aktif_sartlar['min_beton']}
                    
                    Lütfen projeyi; kot uyumu, akslar, merdiven basamakları ({basamak} adet), kolon taramaları ({tarama} adet), paspayı, drenaj ve statik rapor uyumu açısından detaylıca incele.
                    Kesinlikle geçerli bir JSON formatında yanıt ver. JSON anahtarları:
                    - "mimari_maddeler": sözlük (Madde adı: {{"cevap": "EVET/HAYIR", "dogru_mu": true/false, "detay": "Gerekçe"}})
                    - "statik_maddeler": sözlük
                    - "yonetmelik_ekleri": sözlük
                    - "resmi_unsurlar": sözlük
                    """
                    
                    user_prompt = [
                        {"type": "text", "text": f"Statik Rapor Özeti: {pdf_metni[:3000]}\nİdari Evrak Özeti: {idari_metin[:2000]}\nOtomatik Bulgular -> Merdiven: {basamak}, Tarama: {tarama}, Mühendislik Detayları: {eng_details}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                    ]
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                        response_format={"type": "json_object"},
                        temperature=0.3
                    )
                    
                    result_json = json.loads(response.choices[0].message.content)
                    st.session_state.audit_data = result_json
                    
                    report_prompt = "Yüklenen mimari ve statik projeler incelenmiştir. Resmi yapı denetim eksiklik ve onay raporunu Markdown formatında detaylıca yaz."
                    report_res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": report_prompt}],
                        max_tokens=2500
                    )
                    st.session_state.master_report = report_res.choices[0].message.content
                    st.success("✅ Kapsamlı mühendislik denetimi ve AI raporu başarıyla tamamlandı!")
            else:
                st.warning("⚠️ Lütfen önce 1. Adım ile DXF dosyasını görselleştirin.")

    except Exception as e:
        st.error(f"Dosya işleme hatası: {e}")

# --- 8. RAPOR VE İNTERAKTİF MATRİS GÖSTERİMİ ---
if st.session_state.master_report and st.session_state.audit_data:
    st.markdown("---")
    st.header("📑 Resmi Mühendislik İnceleme Tutanağı")
    st.markdown(st.session_state.master_report)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.download_button(
            label="📥 Tutanağı İndir (.md)",
            data=st.session_state.master_report,
            file_name="Muhendislik_Inceleme_Tutanagi.md",
            mime="text/markdown",
            use_container_width=True
        )
    with col_btn2:
        if st.button("📊 İnteraktif Matrisi Aç/Kapat", use_container_width=True):
            st.session_state.show_interactive_form = not st.session_state.get('show_interactive_form', False)

    if st.session_state.get('show_interactive_form', False):
        st.markdown("---")
        st.header("📋 İNTERAKTİF MÜHENDİSLİK VE PROJE MATRİSİ")
        
        def render_clean_interactive_section(section_title, data_dict):
            st.subheader(section_title)
            for madde_adi, info in data_dict.items():
                cevap = info.get("cevap", "EVET")
                dogru_mu = info.get("dogru_mu", False)
                detay = info.get("detay", "Detay yok.")
                
                col_m1, col_m2 = st.columns([4, 1])
                with col_m1:
                    st.markdown(f"**{madde_adi}**")
                with col_m2:
                    if dogru_mu: st.markdown(f"🟢 **{cevap}**")
                    else: st.markdown(f"🔴 **{cevap}**")
                
                if not dogru_mu:
                    with st.expander(f"⚠️ Teknik Gerekçeyi Gör"):
                        st.error(f"**Gerekçe:** {detay}")
                st.markdown("---")

        audit_d = st.session_state.audit_data
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            render_clean_interactive_section("1️⃣ Mimari Kriterler", audit_d.get("mimari_form_maddeleri", {}))
        with col_f2:
            render_clean_interactive_section("2️⃣ Statik ve Betonarme Kriterleri", audit_d.get("statik_form_maddeleri", {}))

        col_f3, col_f4 = st.columns(2)
        with col_f3:
            render_clean_interactive_section("3️⃣ Yönetmelik Ekleri", audit_d.get("yonetmelik_ekleri", {}))
        with col_f4:
            render_clean_interactive_section("4️⃣ Resmi Unsurlar", audit_d.get("resmi_unsurlar", {}))