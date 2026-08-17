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

# --- YENİ MÜHENDİSLİK FONKSİYONLARI ---
def check_merdiven_ve_tarama(dxf_path):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in ['merdiven', 'stairs']])
    tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in ['kolon', 'column', 'st-kolon']])
    return basamak, tarama

def compare_dxf_layers(mimari_path, statik_path):
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

# --- ANA ARAYÜZ VE API ---
st.title("🏛️ Belediye İmar ve Plan-Proje İnceleme Bürosu - Kapsamlı Akıllı Denetim Masası")

with st.sidebar:
    st.subheader("🔑 Kullanıcı API Ayarları")
    user_api_key = st.text_input("OpenAI API Anahtarınız:", type="password")
    if not user_api_key: st.stop()

client = OpenAI(api_key=user_api_key)

# (BELEDIYE_VERITABANI ve diğer fonksiyonların burada sabit kalıyor...)
# ... (Senin paylaştığın mevcut fonksiyonlar buraya gelecek) ...

# --- KONTROL BUTONU ---
if st.button("🏛️ Kapsamlı Mühendislik ve Kot/Aks Denetimini Başlat"):
    # 1. Dosyaları işle
    with open("temp_m.dxf", "wb") as f: f.write(mimari_dxf.getvalue())
    with open("temp_s.dxf", "wb") as f: f.write(statik_dxf.getvalue())
    
    # 2. Otomatik Mühendislik Bulguları
    basamak, tarama = check_merdiven_ve_tarama("temp_m.dxf")
    
    st.subheader("🛠️ Otomatik Mühendislik Bulguları")
    c1, c2 = st.columns(2)
    c1.metric("Merdiven Basamak", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA")
    c2.metric("Kolon Taraması", "Tespit Edildi" if tarama > 0 else "Eksik")
    
    # 3. Çakıştırma Analizi
    st.subheader("🔍 Mimari (Mavi) - Statik (Kırmızı) Çakıştırma")
    st.image(compare_dxf_layers("temp_m.dxf", "temp_s.dxf"), caption="Görsel Koordinasyon Analizi")
    
    # 4. Mevcut AI Analizini Çalıştır
    st.session_state.audit_data = run_master_audit(mimari_dxf, statik_dxf, statik_rapor, idari_evraklar, secilen_belediye_profil)
    
    # (Bundan sonrası mevcut raporlama mantığın ile devam ediyor...)