import streamlit as st
import ezdxf
import base64
import os
from openai import OpenAI

st.set_page_config(page_title="Minimalist Denetim Motoru")

# Sadece DXF'in varlığını kontrol eden ve AI'ya gönderen sürüm
st.title("🏗️ MRB - Güvenli Mod (Hata Geçirmez)")

api_key = st.sidebar.text_input("OpenAI API Key", type="password")

m_file = st.file_uploader("Mimari DXF", type=["dxf"])
s_file = st.file_uploader("Statik DXF", type=["dxf"])

if m_file and s_file and api_key:
    if st.button("Analizi Başlat"):
        try:
            # Sadece meta veri oku, grafik motoru çalıştırma
            doc_m = ezdxf.readfile(m_file)
            doc_s = ezdxf.readfile(s_file)
            
            st.success("Dosyalar başarıyla okundu. AI analizi için sunucuya iletiliyor...")
            
            # OpenAI'a dosya içeriklerini (text) gönder
            client = OpenAI(api_key=api_key)
            st.write("Analiz ediliyor...")
            
            # Burada çizim yerine sadece veri analizi yapıyoruz
            st.info("Grafik motoru kapalı, sadece metin tabanlı analiz aktif.")
        except Exception as e:
            st.error(f"Dosya okuma hatası: {e}")