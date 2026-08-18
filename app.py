import streamlit as st
import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import io

# Sayfa Ayarları
st.set_page_config(layout="wide", page_title="Master Denetim Motoru - Mühendislik Modülü")

# --- GELİŞMİŞ ANALİZ FONKSİYONLARI ---
def check_merdiven_ve_tarama(dxf_path):
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        # Katman adlarını genişlettik
        merdiven_layer_names = ['merdiven', 'stairs', 'merdiven-basamak', 'stairs-steps', 'merdiven-plan']
        tarama_layer_names = ['kolon', 'column', 'st-kolon', 'betonarme', 'kolon-tarama']
        
        basamak = len([l for l in msp.query('LINE') if l.dxf.layer.lower() in merdiven_layer_names])
        tarama = len([h for h in msp.query('HATCH') if h.dxf.layer.lower() in tarama_layer_names])
        return basamak, tarama
    except: return 0, 0

def compare_dxf_layers(mimari_path, statik_path):
    """Görselleştirme sorunlarını çözmek için daha sağlam bir çizim yöntemi."""
    try:
        doc_m = ezdxf.readfile(mimari_path)
        doc_s = ezdxf.readfile(statik_path)
        
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Çizim ayarlarını optimize et
        def draw_dxf(doc, color, ax):
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(doc.modelspace(), finalize=True)
            for artist in ax.get_children():
                if hasattr(artist, 'set_color'): artist.set_color(color)
        
        draw_dxf(doc_m, 'blue', ax)
        draw_dxf(doc_s, 'red', ax)
        
        img_path = "comparison.png"
        plt.savefig(img_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        return img_path
    except Exception as e:
        st.error(f"Görselleştirme hatası: {e}")
        return None

# --- ARAYÜZ ---
st.title("🏛️ Yapı Denetim Uzman Mühendislik Modülü")

col1, col2 = st.columns(2)
with col1:
    mimari_dxf = st.file_uploader("Mimari Proje (DXF)", type=["dxf"], key="m")
with col2:
    statik_dxf = st.file_uploader("Statik Proje (DXF)", type=["dxf"], key="s")

if st.button("🏗️ Kapsamlı Mühendislik Analizini Başlat"):
    if mimari_dxf and statik_dxf:
        with open("m.dxf", "wb") as f: f.write(mimari_dxf.getvalue())
        with open("s.dxf", "wb") as f: f.write(statik_dxf.getvalue())
        
        # 1. Mühendislik Bulguları
        basamak, tarama = check_merdiven_ve_tarama("m.dxf")
        st.subheader("🛠️ Otomatik Mühendislik Bulguları")
        c1, c2 = st.columns(2)
        c1.metric("Merdiven Basamak", f"{basamak} Adet", "Uygun" if basamak >= 17 else "HATA (<17)")
        c2.metric("Kolon Taraması", "Tespit Edildi" if tarama > 0 else "Eksik")
        
        # 2. Çakıştırma
        st.subheader("🔍 Mimari-Statik Çakıştırma Analizi")
        with st.spinner("Çizimler üst üste bindiriliyor..."):
            img = compare_dxf_layers("m.dxf", "s.dxf")
            if img:
                st.image(img, caption="Mavi: Mimari, Kırmızı: Statik")
            else:
                st.error("Çizim motoru dosyayı render edemedi. DXF dosyanızın blok yapısı karmaşık olabilir.")
    else:
        st.warning("Lütfen her iki DXF dosyasını da yükleyin.")