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

# --- ŞİFRE KORUMASI ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    if not st.session_state.password_correct:
        st.title("🔐 MRB Mimarlık - Denetim Motoru Giriş")
        password = st.text_input("Şifreyi Giriniz:", type="password")
        if st.button("Giriş Yap"):
            if password == "MRB_Mimarlık_123":
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("❌ Hatalı Şifre!")
        return False
    return True

if not check_password():
    st.stop()

# --- YENİ MÜHENDİSLİK FONKSİYONLARI ---
def check_merdiven_ve_tarama(dxf_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs']])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
        return basamak, tarama
    except Exception:
        return 0, 0

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
    except Exception:
        return None

# --- ANA EKRAN VE KULLANICI API GİRİŞİ ---
st.title("🏛️ Belediye İmar e Plan-Proje İnceleme Bürosu - Kapsamlı Akıllı Denetim Masası")

with st.sidebar:
    st.subheader("🔑 Kullanıcı API Ayarları")
    st.info("Denetim motorunu kullanmak için OpenAI API anahtarınızı giriniz.")
    user_api_key = st.text_input("OpenAI API Anahtarınız:", type="password")
    if not user_api_key:
        st.warning("Devam etmek için API anahtarınızı girin.")
        st.stop()

client = OpenAI(api_key=user_api_key)

# --- 1. BELEDİYE VERİTABANI ---
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

# --- 2. YARDIMCI FONKSİYONLAR ---
def read_pdf_text(uploaded_file):
    try:
        pdf_bytes = uploaded_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text if text.strip() else "PDF dosyasından metin çıkarılamadı."
    except Exception as e:
        return f"PDF okuma hatası: {e}"

def dxf_to_image(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        msp = doc.modelspace()
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)
        img_path = "temp_dxf_render.png"
        plt.savefig(img_path, dpi=150)
        plt.close(fig)
        with open(img_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception:
        return None

def analyze_dxf_structure(dxf_filepath):
    try:
        doc = ezdxf.readfile(dxf_filepath)
        layers = [layer.dxf.name.lower() for layer in doc.layers]
        texts = [e.dxf.text.strip() for e in doc.modelspace().query('TEXT MTEXT') if e.dxf.text.strip()]
        return layers, texts
    except Exception:
        return [], []

def check_dosya_eksikleri(mimari_file, statik_file, rapor_file, idari_file):
    eksikler = []
    if not mimari_file: eksikler.append("Mimari Proje (DXF)")
    if not statik_file: eksikler.append("Statik Proje (DXF)")
    if not rapor_file: eksikler.append("Statik Hesap Raporu")
    if not idari_file: eksikler.append("İmar Durumu / Aplikasyon / Plankote")
    return eksikler

# --- 3. MASTER DENETİM MOTORU ---
def run_master_audit(mimari_file, statik_file, statik_rapor_file, idari_file, secilen_belediye):
    m_layers, m_texts, s_layers, s_texts = [], [], [], []
    m_img_b64 = None
    rapor_icerigi = "Statik hesap raporu yüklenmedi."
    idari_icerigi = "İdari evraklar yüklenmedi."

    belediye_kriterleri = BELEDIYE_VERITABANI.get(secilen_belediye, BELEDIYE_VERITABANI["Bakanlık Standartları (Genel PAİY & TBDY 2018) [Varsayılan]"])

    if mimari_file:
        tmp_m = "temp_mimari.dxf"
        with open(tmp_m, "wb") as f: f.write(mimari_file.getvalue())
        m_layers, m_texts = analyze_dxf_structure(tmp_m)
        m_img_b64 = dxf_to_image(tmp_m)

    if statik_file:
        tmp_s = "temp_statik.dxf"
        with open(tmp_s, "wb") as f: f.write(statik_file.getvalue())
        s_layers, s_texts = analyze_dxf_structure(tmp_s)

    if statik_rapor_file:
        if statik_rapor_file.name.endswith('.pdf'):
            rapor_icerigi = read_pdf_text(statik_rapor_file)[:6000]
        else:
            try:
                rapor_icerigi = statik_rapor_file.getvalue().decode("utf-8", errors="ignore")[:6000]
            except Exception:
                rapor_icerigi = "Rapor okunurken hata oluştu."

    if idari_file:
        if idari_file.name.endswith('.pdf'):
            idari_icerigi = read_pdf_text(idari_file)[:4000]
        else:
            try:
                idari_icerigi = idari_file.getvalue().decode("utf-8", errors="ignore")[:4000]
            except Exception:
                idari_icerigi = "İdari evrak okunamadı."

    system_prompt = f"""
    Sen kıdemli bir İnşaat Mühendisi ve Belediye İmar Baş Kontrolörüsün.
    Seçilen İdare / Belediye: {secilen_belediye}
    Belediyeye Özel Teknik ve İmar Şartları: {belediye_kriterleri['ozel_sartlar']}
    Asgari Beton Sınırı: {belediye_kriterleri['min_beton']}
    
    YAPILACAK ÖZEL MÜHENDİSLİK KONTROLLERİ:
    1. KOT UYUM TAHKİKİ: Mimari ve statik kat kotlarının uyumu.
    2. AKS UZUNLUĞU VE GEOMETRİ: Aks akışları ve mesafelerinin tutarlılığı.
    3. BACA, ŞAFT VE MENFEZ: Tesisat boşlukları ve şaft kontrolleri.
    
    Kesinlikle geçerli bir JSON formatında yanıt ver. JSON anahtarları:
    - "mimari_maddeler": sözlük (Her madde için: {{"cevap": "EVET/HAYIR", "dogru_mu": true/false, "detay": "gerekçe"}} )
    - "statik_maddeler": sözlük
    - "yonetmelik_ekleri": sözlük
    - "resmi_unsurlar": sözlük
    """

    user_prompt = f"""
    Mimari Metinler Örnekleri: {json.dumps(m_texts[:250], ensure_ascii=False)}
    Statik Metinler Örnekleri: {json.dumps(s_texts[:250], ensure_ascii=False)}
    Statik Hesap Raporu Metni: {rapor_icerigi}
    İdari Evrak Metni: {idari_icerigi}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    if m_img_b64:
        messages.append({"role": "user", "content": [{"type": "text", "text": "Mimari Proje Çizim Görseli:"}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{m_img_b64}"}}]})

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result_json = json.loads(completion.choices[0].message.content)
        return {
            "secilen_belediye": secilen_belediye,
            "mimari_form_maddeleri": result_json.get("mimari_maddeler", {}),
            "statik_form_maddeleri": result_json.get("statik_maddeler", {}),
            "yonetmelik_ekleri": result_json.get("yonetmelik_ekleri", {}),
            "resmi_form_unsurlari": result_json.get("resmi_unsurlar", {})
        }
    except Exception as e:
        return {
            "secilen_belediye": secilen_belediye,
            "mimari_form_maddeleri": {"Hata": {"cevap": "HAYIR", "dogru_mu": False, "detay": str(e)}},
            "statik_form_maddeleri": {},
            "yonetmelik_ekleri": {},
            "resmi_form_unsurlari": {}
        }

# --- 4. ARAYÜZ ---
st.subheader("⚙️ İdare / Belediye Seçimi")
secilen_belediye_profil = st.selectbox(
    "Denetimin tabi olacağı belediye veya yasal idare:",
    listBELEDIYE_VERITABANI_keys = list(BELEDIYE_VERITABANI.keys()),
    index=0
)

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

if "audit_data" not in st.session_state:
    st.session_state.audit_data = None
if "master_report" not in st.session_state:
    st.session_state.master_report = None
if "show_interactive_form" not in st.session_state:
    st.session_state.show_interactive_form = False

if st.button("🏛️ Kapsamlı Mühendislik ve Kot/Aks Denetimini Başlat"):
    eksik_listesi = check_dosya_eksikleri(mimari_dxf, statik_dxf, statik_rapor, idari_evraklar)
    
    if eksik_listesi:
        st.info(f"ℹ️ **Bilgi:** Şu belgeler yüklenmedi: {', '.join(eksik_listesi)}.")
    
    if mimari_dxf or statik_dxf or statik_rapor or idari_evraklar:
        with st.spinner(f"🔄 '{secilen_belediye_profil}' şartlarıyla kot, aks, baca ve çakıştırma analizi yapılıyor..."):
            
            # Geçici Kayıt ve Otomatik Mühendislik Kontrolleri
            if mimari_dxf:
                with open("temp_m.dxf", "wb") as f: f.write(mimari_dxf.getvalue())
            if statik_dxf:
                with open("temp_s.dxf", "wb") as f: f.write(statik_dxf.getvalue())
            
            if mimari_dxf:
                basamak, tarama = check_merdiven_ve_tarama("temp_m.dxf")
                st.subheader("🛠️ Otomatik Geometrik ve Mühendislik Bulguları")
                c1, c2 = st.columns(2)
                c1.metric("Merdiven Basamak Sayısı", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA (<17)")
                c2.metric("Kolon Taraması (Hatch)", "Tespit Edildi" if tarama > 0 else "Eksik")

            if mimari_dxf and statik_dxf:
                st.subheader("🔍 Mimari (Mavi) - Statik (Kırmızı) Çakıştırma Analizi")
                comp_img_path = compare_dxf_layers("temp_m.dxf", "temp_s.dxf")
                if comp_img_path:
                    st.image(comp_img_path, caption="Mavi: Mimari Proje, Kırmızı: Statik Proje")

            st.session_state.audit_data = run_master_audit(mimari_dxf, statik_dxf, statik_rapor, idari_evraklar, secilen_belediye_profil)
            
            prompt_text = f"""
            Sen kıdemli bir İnşaat Mühendisi ve Ruhsat Denetim Komisyon Başkanısın.
            Seçilen Belediye: {secilen_belediye_profil}
            Resmi yapı denetim eksiklik raporu formatında şu başlıklarla maddelenmiş bir rapor hazırla:
            1. **Kot ve Seviye Uyumsuzlukları (Mimari vs Statik)**
            2. **Aks Uzunlukları ve Geometrik Tutarlılık**
            3. **Baca, Şaft ve Tesisat Boşluğu Kontrolleri**
            4. **Statik ve Betonarme Rapor Eksiklikleri**
            5. **Nihai Komisyon Kararı**
            """
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_text}],
                    max_tokens=2500,
                    timeout=60.0
                )
                st.session_state.master_report = response.choices[0].message.content
                st.session_state.show_interactive_form = False
                st.success("Mühendislik denetim raporu başarıyla oluşturuldu!")
            except Exception as e:
                st.error(f"Sunucu bağlantı hatası: {e}")
    else:
        st.warning("Lütfen denetimi başlatmak için en azından bir proje dosyası yükleyin.")

if st.session_state.master_report and st.session_state.audit_data:
    st.markdown("---")
    st.header("📑 Resmi Mühendislik İnceleme Tutanağı")
    st.markdown(st.session_state.master_report)
    
    st.markdown("---")
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
            st.session_state.show_interactive_form = not st.session_state.show_interactive_form

    if st.session_state.show_interactive_form:
        st.markdown("---")
        st.header("📋 İNTERAKTİF KOT, AKS VE PROJE MATRİSİ")
        
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
                    if dogru_mu:
                        st.markdown(f"🟢 **{cevap}**")
                    else:
                        st.markdown(f"🔴 **{cevap}**")
                
                if not dogru_mu:
                    with st.expander(f"⚠️ Mühendislik Gerekçesini Gör"):
                        st.error(f"**Teknik Gerekçe:** {detay}")
                st.markdown("---")

        audit_d = st.session_state.audit_data
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            render_clean_interactive_section("1️⃣ Mimari Kot ve Aks Kriterleri", audit_d.get("mimari_form_maddeleri", {}))
        with col_f2:
            render_clean_interactive_section("2️⃣ Statik Kalıp ve Kot Uyumu", audit_d.get("statik_form_maddeleri", {}))

        col_f3, col_f4 = st.columns(2)
        with col_f3:
            render_clean_interactive_section("3️⃣ Tesisat, Baca ve Şaftlar", audit_d.get("yonetmelik_ekleri", {}))
        with col_f4:
            render_clean_interactive_section("4️⃣ Resmi Unsurlar", audit_d.get("resmi_form_unsurlari", {}))