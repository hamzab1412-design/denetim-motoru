import streamlit as st
import ezdxf
import io
import gc
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from PIL import Image
import base64
from openai import OpenAI

st.set_page_config(layout="wide")

# Belleği temizleyen render motoru
def secure_render(uploaded_file, output_path, color):
    try:
        # Bellek temizliği
        gc.collect()
        
        # Dosyayı diske yazma, doğrudan bellekte oku
        bytes_data = uploaded_file.getvalue()
        doc = ezdxf.read(io.BytesIO(bytes_data))
        msp = doc.modelspace()

        fig = plt.figure(figsize=(12, 12))
        ax = fig.add_axes([0, 0, 1, 1])
        
        # Basitleştirilmiş Frontend
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        frontend = Frontend(ctx, out)
        
        # Sadece temel geometrileri çiz (yazıları geç)
        for entity in msp:
            if entity.dxftype() in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'):
                frontend.draw_entity(entity, frontend.entity_dxf_attribs(entity))
        
        ax.axis('off')
        fig.savefig(output_path, dpi=150, bbox_inches='tight', transparent=True)
        plt.close(fig)
        
        # Bellek temizliği
        del doc, msp, fig, ax
        gc.collect()
        return True
    except Exception as e:
        st.error(f"Render hatası: {e}")
        return False

# Arayüz
st.title("🏗️ MRB Mimarlık - Bellek Optimize Denetim")
m_file = st.file_uploader("Mimari (DXF)", type=["dxf"], key="m")
s_file = st.file_uploader("Statik (DXF)", type=["dxf"], key="s")

if m_file and st.button("Mimariyi Render Et"):
    if secure_render(m_file, "m.png", 'blue'):
        st.image("m.png")
        st.session_state.m_png = "m.png"

if s_file and st.button("Statiği Render Et"):
    if secure_render(s_file, "s.png", 'red'):
        st.image("s.png")
        st.session_state.s_png = "s.png"

# Overlay ve AI
if st.session_state.get("m_png") and st.session_state.get("s_png"):
    if st.button("🔀 Çakıştır (Overlay)"):
        m = Image.open("m.png").convert("RGBA")
        s = Image.open("s.png").convert("RGBA")
        overlay = Image.alpha_composite(m, s)
        overlay.save("overlay.png")
        st.image("overlay.png")
        
        # AI
        client = OpenAI(api_key=st.sidebar.text_input("API Key", type="password"))
        with open("overlay.png", "rb") as f:
            img = base64.b64encode(f.read()).decode()
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Bu çakışma paftasını incele."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
            ]}]
        )
        st.markdown(res.choices[0].message.content)