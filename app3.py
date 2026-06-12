import streamlit as st
import fitz  # PyMuPDF
import requests
from gtts import gTTS
from langdetect import detect
import json
import pandas as pd
import re

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="PDF Invoice AI Reader", layout="wide")

# =========================
# LIGHT UI + ANIMATIONS
# =========================
st.markdown("""
<style>

body {
    background: #f5f7fb;
    color: #111827;
}

/* Animation */
@keyframes fadeIn {
    from {opacity: 0; transform: translateY(10px);}
    to {opacity: 1; transform: translateY(0);}
}

/* Cards */
.custom-card {
    background: white;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.08);
    animation: fadeIn 0.5s ease-in-out;
    transition: 0.3s;
}

.custom-card:hover {
    transform: scale(1.01);
    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
}

/* Buttons */
.stButton > button {
    width: 100%;
    background: linear-gradient(135deg, #4f46e5, #3b82f6);
    color: white;
    border-radius: 12px;
    padding: 10px;
    font-weight: bold;
    border: none;
    transition: 0.3s;
}

.stButton > button:hover {
    transform: translateY(-2px);
}

/* Text area */
textarea {
    background: https://media.licdn.com/dms/image/v2/C4D0BAQEVSamyhkWrjg/company-logo_200_200/company-logo_200_200/0/1630533089545/stepsoft_gmbh_logo?e=2147483647&v=beta&t=ye2LQYDklvViuSwb331CGPZsomkJaSVBf15rOlYWXag;
    border-radius: 10px !important;
}

h1 {
    text-align: center;
    animation: fadeIn 1s ease-in-out;
}
            

</style>
""", unsafe_allow_html=True)

# =========================
# TITLE
# =========================
st.title("📄 PDF Reader")

# =========================
# OLLAMA FUNCTION
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
# LANGUAGE
# =========================
def detect_language(text):
    try:
        return detect(text)
    except:
        return "en"

def map_lang(lang):
    return {"en":"en","fr":"fr","de":"de","es":"es","it":"it"}.get(lang,"en")

# =========================
# AUDIO
# =========================
def text_to_speech(text, lang):
    tts = gTTS(text=text, lang=lang)
    file = "output.mp3"
    tts.save(file)
    return file

# =========================
# PDF
# =========================
def extract_pages(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    return [page.get_text() for page in doc]

def spell_text(text):
    return " ".join(list(text))

# =========================
# SAFE JSON PARSER
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
        return {"error": "Invalid JSON"}

# =========================
# UPLOAD
# =========================
uploaded_file = st.file_uploader("📤 Upload Invoice PDF", type="pdf")

if uploaded_file:

    pages = extract_pages(uploaded_file)
    full_text = " ".join(pages)

    lang = map_lang(detect_language(full_text))

    # =========================
    # INFO CARD
    # =========================
    st.markdown(f"""
    <div class="custom-card">
        <h3>🌍 Detected Language</h3>
        <p><b>{lang}</b></p>
    </div>
    """, unsafe_allow_html=True)

    # =========================
    # TEXT
    # =========================
    st.markdown("""
    <div class="custom-card">
        <h3>📄 Extracted Text</h3>
    </div>
    """, unsafe_allow_html=True)
    st.text_area("📄 Extracted Text", full_text, height=300, label_visibility="collapsed")

    # =========================
    # BUTTONS
    # =========================
    col1, col2, col3 = st.columns(3)

    # =========================
    # 🧠 ANALYZE INVOICE (JSON ARTICLES)
    # =========================
    with col1:
        if st.button("🧠 Extract Invoice Data"):

            with st.spinner("Analyzing invoice..."):

                prompt = f"""
You are an expert invoice extraction system.

Extract ALL articles from this invoice.

Return STRICT JSON ONLY:

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

                if "articles" in data:

                    st.markdown("### 📦 Extracted Articles")

                    for i, art in enumerate(data["articles"]):

                        st.markdown(f"""
                        <div class="custom-card">
                            <h4>📦 Article {i+1}</h4>
                            <p><b>Artikelnummer:</b> {art.get("artikelnummer")}</p>
                            <p><b>Bezeichnung:</b> {art.get("bezeichnung")}</p>
                            <p><b>Menge:</b> {art.get("menge")}</p>
                            <p><b>Preis:</b> {art.get("preis")}</p>
                            <p><b>Gesamtpreis:</b> {art.get("gesamtpreis")}</p>
                            <p><b>Liefertermin:</b> {art.get("liefertermin")}</p>
                        </div>
                        """, unsafe_allow_html=True)

                    # TABLE VIEW
                    df = pd.DataFrame(data["articles"])
                    st.dataframe(df)

                else:
                    st.error("Failed to parse invoice JSON")

    # =========================
    # 🔊 READ PDF
    # =========================
    with col2:
        if st.button("🔊 Read PDF"):

            with st.spinner("Generating audio..."):

                for i, page in enumerate(pages):
                    if page.strip():
                        audio = text_to_speech(page[:2500], lang)
                        st.write(f"Page {i+1}")
                        st.audio(open(audio, "rb").read())

    # =========================
    # 🔤 SPELL MODE
    # =========================
    with col3:
        if st.button("🔤 Spell PDF"):

            spelled = spell_text(full_text[:2000])
            audio = text_to_speech(spelled, lang)
            st.audio(open(audio, "rb").read())
            st.success("Done ✔")