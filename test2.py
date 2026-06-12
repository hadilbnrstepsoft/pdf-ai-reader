import streamlit as st
import fitz
import pytesseract
from PIL import Image
import io
import requests
import json
import pandas as pd
import re
import camelot
from langdetect import detect
from gtts import gTTS
st.markdown("""
<style>

body {
    background-color: #0f172a;
}

/* TITLE */
h1 {
    text-align: center;
    color: #ffffff;
    font-size: 38px;
    margin-bottom: 20px;
}

/* CARD STYLE */
.card {
    background: #111827;
    padding: 18px;
    border-radius: 16px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    margin-bottom: 15px;
    color: white;
}

/* BUTTON */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    color: white;
    border-radius: 10px;
    padding: 10px;
    font-weight: bold;
    border: none;
}

/* TABLE */
.dataframe {
    background-color: white;
    border-radius: 10px;
}

/* JSON BOX */
.json-box {
    background: #0b1220;
    padding: 15px;
    border-radius: 12px;
    color: #00ffcc;
    font-size: 13px;
    overflow-x: auto;
}

</style>
""", unsafe_allow_html=True)
# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="PDF AI Reader PRO", layout="wide")

st.title("📄 PDF  Reader")

# =========================
# OLLAMA
# =========================
def ask_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

# =========================
# LANGUAGE DETECTION
# =========================
def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

# =========================
# PDF + OCR
# =========================
def extract_pages(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    pages = []

    for page in doc:
        text = page.get_text().strip()

        if len(text) > 20:
            pages.append(text)
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            ocr_text = pytesseract.image_to_string(
                img,
                lang="eng+deu+fra",
                config="--psm 6"
            )
            pages.append(ocr_text)

    return pages

# =========================
# SAFE JSON
# =========================
def safe_json_parse(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {}

# =========================
# TABLE EXTRACTION
# =========================
def extract_tables(file_path):
    tables = camelot.read_pdf(file_path, pages="all")
    return [t.df for t in tables]

# =========================
# 🔥 PROFESSIONAL TABLE DISPLAY
# =========================
def show_tables(tables):
    st.subheader("📊 Extracted Tables (Professional View)")

    for i, df in enumerate(tables):

        st.markdown(f"### 📊 Table {i+1}")

        # CLEAN COLUMN NAMES
        df.columns = [f"Col {i}" for i in range(len(df.columns))]

        # CENTER TABLE STYLE
        styled = df.style.set_properties(**{
            "background-color": "#ffffff",
            "color": "#111827",
            "border": "1px solid #e5e7eb",
            "text-align": "center",
            "padding": "8px"
        }).set_table_styles([
            {"selector": "th", "props": [
                ("background-color", "#2563eb"),
                ("color", "white"),
                ("text-align", "center"),
                ("font-weight", "bold")
            ]}
        ])

        st.dataframe(styled, use_container_width=True)

# =========================
# JSON ARTICLES DISPLAY
# =========================
def show_articles(data):
    if "articles" not in data:
        st.warning("No articles found")
        return

    st.subheader("📦 Articles")

    for i, art in enumerate(data["articles"]):
        st.markdown(f"""
        <div style="
            background:white;
            padding:15px;
            border-radius:12px;
            margin-bottom:10px;
            box-shadow:0 4px 15px rgba(0,0,0,0.1);
        ">
            <h4>📦 Article {i+1}</h4>
            <b>Artikelnummer:</b> {art.get('artikelnummer','')}<br>
            <b>Bezeichnung:</b> {art.get('bezeichnung','')}<br>
            <b>Menge:</b> {art.get('menge','')}<br>
            <b>Preis:</b> {art.get('preis','')}<br>
            <b>Gesamtpreis:</b> {art.get('gesamtpreis','')}<br>
            <b>Liefertermin:</b> {art.get('liefertermin','')}
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📊 Table View")
    st.dataframe(pd.DataFrame(data["articles"]), use_container_width=True)

# =========================
# UPLOAD
# =========================
uploaded_file = st.file_uploader("📤 Upload PDF", type="pdf")

if uploaded_file:

    uploaded_file.seek(0)

    pages = extract_pages(uploaded_file)
    full_text = " ".join(pages)

    lang = detect_language(full_text)

    st.success(f"🌍 Language detected: {lang}")

    # =========================
    # TEXT
    # =========================
    st.subheader("📄 Extracted Text")
    st.text_area("", full_text, height=250)

    col1, col2, col3 = st.columns(3)

    # =========================
    # AI JSON EXTRACTION
    # =========================
    with col1:
        if st.button("🧠 Extract Articles"):

            prompt = f"""
Extract structured invoice JSON.

Return ONLY JSON:

{{
  "articles": [
    {{
      "artikelnummer": "",
      "bezeichnung": "",
      "menge": "",
      "preis": "",
      "gesamtpreis": "",
      "liefertermin": ""
    }}
  ]
}}

TEXT:
{full_text}
"""

            result = ask_ollama(prompt)
            data = safe_json_parse(result)

            show_articles(data)

    # =========================
    # TABLE EXTRACTION
    # =========================
    with col2:
        if st.button("📊 Extract Tables"):

            uploaded_file.seek(0)

            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.read())

            tables = extract_tables("temp.pdf")

            if tables:
                show_tables(tables)
            else:
                st.warning("No tables detected")

    # =========================
    # AUDIO
    # =========================
    with col3:
        if st.button("🔊 Read PDF"):

            audio = "audio.mp3"
            tts = gTTS(text=full_text[:2000], lang="en")
            tts.save(audio)

            st.audio(open(audio, "rb").read())