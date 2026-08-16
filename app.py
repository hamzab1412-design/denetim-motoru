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
st.set_page_config(layout="wide", page_title="Master Denetim Motoru (Esnek Akıllı Analiz)")

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

# --- ANA EKRAN VE API GİRİŞİ ---
st.title("🏛️ Belediye İmar ve Plan-Proje İnceleme Bürosu - Kapsamlı Akıllı Denetim Masası")

with st.sidebar:
    st.subheader("🔑 Kullanıcı API Ayarları")
    st.info("Denetim motorunu kullanmak için OpenAI API anahtarınızı giriniz.")
    user_api_key = st.text_input("OpenAI API Anahtarınız:", type="password")
    if not user_api_key:
        st.warning("Devam etmek için API anahtarınızı girin.")
        st.stop()

# API Anahtarı Entegrasyonu
client = OpenAI(api_key=user_api_key)

# --- 1. ADANA, İSTANBUL VE BALIKESİR TAM BELEDİYE VERİTABANI ---
BELEDIYE_VERITABANI = {
    "Bakanlık Standartları (Genel PAİY & TBDY 2018) [Varsayılan]": {
        "asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30",
        "ozel_sartlar": "Planlı Alanlar İmar Yönetmeliği tam metni ve ulusal teknik yönetmelikler esastır."
    },
    # ADANA İLÇELERİ
    "Adana Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Adana Büyükşehir İmar Yönetmeliği, ana arter nizamı ve toplu ulaşım entegrasyon kuralları geçerlidir."},
    "Adana - Aladağ Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Dağlık bölge yerleşim şartları, kar yükü katsayıları ve eğimli arazi istinat kuralları uygulanır."},
    "Adana - Ceyhan Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Ceyhan bölge imar notları, tarım alanı geçiş sınırları ve sanayi bölgesi yapılaşma esasları dikkate alınır."},
    "Adana - Çukurova Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Çukurova 1/1000 İmar Planı Notları, yerel zemin koşulları, Deprem Bölgeleri Yönetmeliği ve Isı Yalıtım Esasları zorunludur."},
    "Adana - Feke Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Kırsal ve dağlık alan yerleşim normları, yöresel malzeme uyumu gözetilir."},
    "Adana - İmamoğlu Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "İmamoğlu ilçe imar planı notları ve ova tabanı zemin iyileştirme kuralları geçerlidir."},
    "Adana - Karaisalı Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Doğal sit ve vadi koruma geçiş bölgesi yapılaşma şartları uygulanır."},
    "Adana - Karataş Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Kıyı kanunu, deniz kenarı yapılaşma sınırları, yüksek taban suyu ve korozyon önlem tedbirleri zorunludur."},
    "Adana - Kozan Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Kozan tarihi kent dokusu geçiş sınırları ve bölgesel imar planı notları uygulanır."},
    "Adana - Pozantı Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Yaylalık alan imar yönetmeliği, çatı eğim oranları ve yoğun kar yükü hesapları esastır."},
    "Adana - Saimbeyli Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Dağlık bölge topoğrafya uyum kuralları ve yerel yapı nizamı geçerlidir."},
    "Adana - Sarıçam Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Üniversite bölge planı, yeni yerleşim aksları ve genişleme sahası imar notları uygulanır."},
    "Adana - Seyhan Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Seyhan Belediyesi Bölge İmar Notları, tarihi silüet ve estetik komisyonu kararları dikkate alınır."},
    "Adana - Tufanbeyli Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Sert iklim şartları, ısı yalıtım detayları ve ilçe merkezi yapılaşma notları geçerlidir."},
    "Adana - Yumurtalık Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Sahil kenarı yapılaşma sınırları, turizm bölgesi notları ve korozyon dayanım şartları zorunludur."},
    "Adana - Yüreğir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Yüreğir imar planı notları, kentsel dönüşüm bölgesi kriterleri ve toplu konut nizamı geçerlidir."},

    # İSTANBUL İLÇELERİ
    "İstanbul Büyükşehir Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "İBB İmar Yönetmeliği, boğaziçi öngörünüm kuralları ve akustik rapor zorunluluğu vardır."},
    "İstanbul - Kadıköy Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Kadıköy bölgesel imar notları, otopark yönetmeliği ek şartları ve akustik rapor zorunluluğu vardır."},
    "İstanbul - Beşiktaş Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Beşiktaş kentsel sit alanı geçiş dönemi yapılanma şartları ve estetik komisyonu onayları esastır."},
    "İstanbul - Şişli Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Merkezi iş alanı yüksek katlı yapılaşma, rüzgar tüneli analizi ve otopark yönetmeliği uygulanır."},
    "İstanbul - Üsküdar Belediyesi": {"asansor_min": 1.50, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Boğaziçi silüet koruma sınırları ve estetik komisyon onayı zorunludur."},
    "İstanbul - Esenyurt Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Yüksek katlı bloklar arası mesafe tahkikleri ve otopark yönetmeliği tam uyum denetlenir."},

    # BALIKESİR İLÇELERİ
    "Balıkesir Büyükşehir Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Balıkesir Büyükşehir İmar Yönetmeliği, kırsal kalkınma ve turizm bölgesi yapılaşma genel esasları geçerlidir."},
    "Balıkesir - Edremit Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Kazdağları etekleri koruma sınırları, Altınoluk/Akçay sahil şeridi yapılaşma şartları uygulanır."},
    "Balıkesir - Bandırma Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C35", "ozel_sartlar": "Bandırma liman ve sanayi bölgesi etkileşim imar notları, körfez rüzgar yükü hesapları esastır."},
    "Balıkesir - Ayvalık Belediyesi": {"asansor_min": 1.48, "asansor_max": 5.00, "min_beton": "C30", "ozel_sartlar": "Kentsel ve doğal sit alanı, tarihi Ayvalık taştan evler doku koruma kuralları uygulanır."}
}

TERIM_SOZLUGU = {
    "yerlesim": ["yerleşim", "zemin aplikasyon", "aplikasyon kroki", "vaziyet ve yerleşim", "zem. apl."],
    "baca": ["baca", "şimiş", "havalandırma bacası", "davlumbaz borusu"],
    "kolon": ["kolon", "sütun", "tasiyici", "k"],
    "perde": ["perde", "p", "betonarme perde"],
    "pis_su": ["pis su", "çukur", "rögar", "foseptik"]
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
    rapor_icerigi = "Statik hesap raporu yüklenmedi. Lütfen DXF çizimlerindeki etiket, not ve katmanlara göre değerlendir."
    idari_icerigi = "İdari evraklar yüklenmedi. Lütfen DXF çizimlerindeki notlara göre değerlendir."

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

    all_texts = m_texts + s_texts
    all_layers = m_layers + s_layers

    system_prompt = f"""
    Sen kıdemli bir Belediye İmar ve Yapı Denetim Baş Komisyon Başkanısın.
    Seçilen İdare / Belediye: {secilen_belediye}
    Belediyeye Özel Teknik ve İmar Şartları: {belediye_kriterleri['ozel_sartlar']}
    Asgari Beton Sınırı: {belediye_kriterleri['min_beton']}
    Kullanılan Eş Anlamlılar Sözlüğü (Alias): {TERIM_SOZLUGU}
    
    ÖNEMLİ DENETİM KURALI:
    - Eğer bir statik hesap raporu veya idari evrak PDF olarak yüklenmemişse, doğrudan her şeye "belirtilmemiştir" diyerek başarısız kabul etme.
    - DXF çizimlerinin içindeki metin bloklarında (TEXT/MTEXT), katmanlarda (layers) veya çizim notlarında (örn. C30, asmolen, yerleşim, rampa vb.) ilgili kurala dair herhangi bir ibare veya anlam bütünlüğü varsa bunu "EVET" ve "doğru_mu: true" olarak değerlendir.
    - Sadece projede açıkça bir eksiklik veya bariz bir yönetmelik aykırılığı tespit ettiğinde "HAYIR" ver. Aşırı şüpheci olma, yapıcı ve esnek bir denetim yaklaşımı sergile.
    
    Kesinlikle geçerli bir JSON formatında yanıt ver. JSON şu anahtarları içermelidir:
    - "mimari_maddeler": sözlük (Her madde için: {{"cevap": "EVET/HAYIR", "dogru_mu": true/false, "detay": "gerekçe"}} )
    - "statik_maddeler": sözlük
    - "yonetmelik_ekleri": sözlük
    - "resmi_unsurlar": sözlük
    """

    user_prompt = f"""
    Statik Hesap Raporu Metni: {rapor_icerigi}
    İdari Evrak Metni: {idari_icerigi}
    Tespit Edilen Katmanlar: {all_layers[:50]}
    Metin Havuzu Örnekleri: {json.dumps(all_texts[:400], ensure_ascii=False)}

    Değerlendirilecek Başlıklar:
    1. Mimari Maddeler:
       - PAİY Md. 5-6 (Vaziyet Planı ve Röperli Kot Esasları, 0.00 kotu vb.)
       - PAİY Md. 18-20 (Yapı Yaklaşma Sınırları ve Çekme Mesafeleri)
       - Mimari Kriter: Zemin Aplikasyon / Yerleşim Planı Adlandırması
       - Mimari Kriter: Sığınak Merdiveni 17 Basamak Kuralı
       - Mimari Kriter: Rampa Eğimi Tahkiki (16-50 cm arası max %7)
       - Mimari Kriter: Kapı ve Pencerelerin Detaylandırılması (p1, k1 vb.)
       - Mimari Kriter: Çatı Katı Bacalar (Dam seviyesinden min 75 cm)
       - Mimari Kriter: Isı Hesap Raporu İbaresi
       - Yangın Yönetmeliği Kriteri: Kaçış Kapılarının Dışa Açılması
       - PAİY Md. 26 (1/50 Ölçekli Kat Planı ve Kesit Düzeni)
    2. Statik Maddeler:
       - Statik Kriter: Temel Aplikasyon Planına Pis Su Çukuru Yeri
       - Statik Kriter: Beton ve Donatı Çeliği Kalitesi Yazımı (Min. {belediye_kriterleri['min_beton']} uyumu)
       - Statik Kriter: Kalıp Planı Katsayıları (A0, I, R, Zemin Sınıfı)
       - Statik Kriter: Tüm Çizimlerde Paspayı Gösterimi
       - Statik Kriter: Asmolen / Dişli Döşeme Tabla Beton Kalınlığı (min 7 cm)
       - Statik Kriter: Kolon-Kiriş Düğüm Noktası Kesme Güvenliği
       - Statik Kriter: Mimari-Statik Kat Yükseklik Uyumsuzluğu
       - TBDY 2018 Bölüm 16 (Radye Temel ve Bağ Kirişi Detayları)
    3. Yönetmelik Ekleri:
       - Otopark Yönetmeliği (Daire Başına Asgari Araç Yeri Sayısı)
       - Otopark Yönetmeliği (Engelli Otopark Yeri Ayrılması)
       - Sığınak Yönetmeliği (Brüt Alan Oranı ve Kişi Başı Tahkik)
       - Yangın Yönetmeliği (Kaçış Merdiveni Sayısı ve Genişliği)
    4. Resmi Unsurlar:
       - Yapı Ruhsatı Formu Proje Müellifi Kimlik Bilgileri
       - Oda Sicil ve Büro Tescil Belgesi Numaraları

    Her madde için:
    - 'cevap': Projede veya metinlerde o unsur geçiyorsa "EVET", yoksa "HAYIR".
    - 'dogru_mu': Standartlara uygunsa true, eksik veya hatalıysa false.
    - 'detay': Profesyonel yapı denetim dilinde somut gerekçe.
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
            temperature=0.3  # Esnekliği artırmak için 0.3 yapıldı
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
        st.error(f"Master AI analiz hatası: {e}")
        return {
            "secilen_belediye": secilen_belediye,
            "mimari_form_maddeleri": {"Hata": {"cevap": "HAYIR", "dogru_mu": False, "detay": str(e)}},
            "statik_form_maddeleri": {},
            "yonetmelik_ekleri": {},
            "resmi_form_unsurlari": {}
        }

# --- 4. ARAYÜZ VE AKILLI BELEDİYE ARAMA KUTUSU ---
st.subheader("⚙️ İdare / Belediye Seçimi (Adana, İstanbul, Balıkkesir)")
secilen_belediye_profil = st.selectbox(
    "Denetimin tabi olacağı belediye veya yasal idare:",
    list(BELEDIYE_VERITABANI.keys()),
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

# Session States
if "audit_data" not in st.session_state:
    st.session_state.audit_data = None
if "master_report" not in st.session_state:
    st.session_state.master_report = None
if "show_interactive_form" not in st.session_state:
    st.session_state.show_interactive_form = False

# --- 5. İŞLEMİ BAŞLAT ---
if st.button("🏛️ Kapsamlı Master Denetimini Başlat"):
    eksik_listesi = check_dosya_eksikleri(mimari_dxf, statik_dxf, statik_rapor, idari_evraklar)
    
    if eksik_listesi:
        st.info(f"ℹ️ **Bilgi:** Şu belgeler yüklenmedi: **{', '.join(eksik_listesi)}**. Sistem analizi mevcut DXF çizimlerindeki etiketler ve notlar üzerinden esnek olarak yürütecektir.")
    
    if mimari_dxf or statik_dxf or statik_rapor or idari_evraklar:
        with st.spinner(f"🔄 '{secilen_belediye_profil}' şartlarıyla projeler esnek ve akıllı olarak inceleniyor..."):
            st.session_state.audit_data = run_master_audit(mimari_dxf, statik_dxf, statik_rapor, idari_evraklar, secilen_belediye_profil)
            
            prompt_text = f"""
            Sen belediye imar müdürlüğünde görev yapan en kıdemli Baş Ruhsat Denetim Komisyon Başkanısın.
            Seçilen Belediye/İdare: {secilen_belediye_profil}
            Özel İmar Şartları: {aktif_sartlar['ozel_sartlar']}
            
            GÖREV: Yüklenen projelerin ve raporların analizi tamamlanmıştır. 
            Düz paragraf metinleri yazma. Resmi yapı denetim kurumlarının eksiklik raporlarında olduğu gibi, başlıklar altında **maddelenmiş (bullet points) ve net teknik gerekçeler içeren** bir İnceleme Tutanağı ve Eksiklik Listesi hazırla.
            
            Şu ana başlıkları kullan:
            1. **Dosya ve İdari Eksiklikler**
            2. **Mimari Proje Uyumluluk Hataları**
            3. **Statik Proje ve Hesap Raporu Eksiklikleri**
            4. **Otopark, Sığınak ve Tesisat Uyumsuzlukları**
            5. **Nihai Komisyon Kararı ve Düzeltme İkazı**
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
                st.success("Kapsamlı denetim raporu başarıyla oluşturuldu!")
            except Exception as e:
                st.error(f"Sunucu bağlantı hatası: {e}")
    else:
        st.warning("Lütfen denetimi başlatmak için en azından bir proje veya rapor dosyası yükleyin.")

# --- RENDER RESULTS ---
if st.session_state.master_report and st.session_state.audit_data:
    st.markdown("---")
    st.header("📑 Resmi İnceleme Tutanağı ve Eksiklik Listesi")
    st.markdown(st.session_state.master_report)
    
    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        st.download_button(
            label="📥 Resmi İnceleme Tutanağını İndir (.md)",
            data=st.session_state.master_report,
            file_name="Resmi_Inceleme_Tutanagi.md",
            mime="text/markdown",
            use_container_width=True
        )
        
    with col_btn2:
        if st.button("📊 İnteraktif Resmi Formu ve Matrisi Aç/Kapat", use_container_width=True):
            st.session_state.show_interactive_form = not st.session_state.show_interactive_form

    # --- İNTERAKTİF FORM GÖRÜNÜMÜ ---
    if st.session_state.show_interactive_form:
        st.markdown("---")
        st.header("📋 İNTERAKTİF RESMİ RUHSAT İNCELEME FORM MATRİSİ")
        st.info("💡 **Bilgi:** Aşağıdaki resmi form matrisinde maddelerin durumuna göre **EVET** veya **HAYIR** yazar. Esnek analize göre uygun ve **doğru** olanlar **Yeşil**, hatalı veya eksik olduğu için **yanlış** olanlar **Kırmızı** renkte gösterilmektedir. Kırmızı yazan hatalı maddelerin üzerine tıklayarak yapı denetim gerekçesini okuyabilirsiniz.")

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
                    with st.expander(f"⚠️ Yapı Denetim Gerekçesini Gör (Tıkla)"):
                        st.error(f"**Teknik Hata Gerekçesi:** {detay}")
                st.markdown("---")

        audit_d = st.session_state.audit_data
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            render_clean_interactive_section("1️⃣ Mimari Proje İnceleme Formu", audit_d.get("mimari_form_maddeleri", {}))
        with col_f2:
            render_clean_interactive_section("2️⃣ Statik Proje İnceleme Formu", audit_d.get("statik_form_maddeleri", {}))

        col_f3, col_f4 = st.columns(2)
        with col_f3:
            render_clean_interactive_section("3️⃣ Otopark, Sığınak ve Yangın Yönetmeliği", audit_d.get("yonetmelik_ekleri", {}))
        with col_f4:
            render_clean_interactive_section("4️⃣ Resmi Ruhsat Formu ve Müellif Unsurları", audit_d.get("resmi_form_unsurlari", {}))