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
from PIL import Image

st.set_page_config(layout="wide", page_title="MRB Mimarlık - Profesyonel Denetim")

# --- 1. ŞİFRE ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    if st.text_input("Şifre", type="password") == "MRB_Mimarlık_123":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 2. HATA VERMEYEN PROFESYONEL RENDER MOTORU ---
def render_autocad_style(dxf_path, output_path, line_color='black'):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    fig = plt.figure(figsize=(15, 15))
    ax = fig.add_axes([0, 0, 1, 1])
    
    # Font hatası veren MTEXT/TEXT öğelerini geçici olarak süzerek (gizleyerek) çizdiriyoruz
    # Böylece AutoCAD geometrisi, çizgileri, kolonları ve taramaları tam olarak görünür
    class SafeFrontend(Frontend):
        def draw_mtext_entity(self, entity, properties):
            pass # Yazı hatasını engellemek için pas geç
        def draw_text_entity(self, entity, properties):
            pass # Yazı hatasını engellemek için pas geç

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    frontend = SafeFrontend(ctx, out)
    frontend.draw_layout(msp, finalize=True)
    
    ax.set_aspect('equal')
    ax.axis('off')
    fig.savefig(output_path, dpi=300, bbox_inches='tight', transparent=True)
    plt.close(fig)

# --- 3. ARAYÜZ ---
st.title("🏗️ MRB Mimarlık - Profesyonel AutoCAD Pafta İnceleme")
col1, col2 = st.columns(2)

m_file = col1.file_uploader("Mimari (DXF)", type=["dxf"], key="m")
s_file = col2.file_uploader("Statik (DXF)", type=["dxf"], key="s")

if m_file:
    with open("m.dxf", "wb") as f: f.write(m_file.getvalue())
    if st.button("🖼️ Mimariyi AutoCAD Gibi Render Et"):
        with st.spinner("Pafta işleniyor..."):
            render_autocad_style("m.dxf", "m_render.png")
            st.image("m_render.png", caption="Mimari Pafta (AutoCAD Kalitesinde)")
            st.session_state.m_png = "m_render.png"

if s_file:
    with open("s.dxf", "wb") as f: f.write(s_file.getvalue())
    if st.button("🖼️ Statiği AutoCAD Gibi Render Et"):
        with st.spinner("Pafta işleniyor..."):
            render_autocad_style("s.dxf", "s_render.png")
            st.image("s_render.png", caption="Statik Pafta (AutoCAD Kalitesinde)")
            st.session_state.s_png = "s_render.png"

# --- 4. OVERLAY VE ANALİZ ---
if st.session_state.get("m_png") and st.session_state.get("s_png"):
    if st.button("🔀 Projeleri Çakıştır (Overlay)"):
        m = Image.open("m_render.png").convert("RGBA")
        s = Image.open("s_render.png").convert("RGBA")
        
        # Mimariyi mavi, statiği kırmızı yap
        m_blue = Image.new("RGBA", m.size, (0, 0, 255, 255))
        m = Image.composite(m_blue, m, m.split()[3]) 
        s_red = Image.new("RGBA", s.size, (255, 0, 0, 255))
        s = Image.composite(s_red, s, s.split()[3])
        
        overlay = Image.alpha_composite(m, s)
        overlay.save("overlay.png")
        st.image("overlay.png", caption="Çakışma Paftası (Mavi: Mimari, Kırmızı: Statik)")

    if st.button("🤖 AI ile Detaylı Çakışma Raporu"):
        client = OpenAI(api_key=st.sidebar.text_input("API Key", type="password"))
        with open("overlay.png", "rb") as f:
            img = base64.b64encode(f.read()).decode()
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Bu overlay görselinde aks ve kolon çakışmalarını detaylıca raporla."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
            ]}]
        )
        st.markdown(res.choices[0].message.content)