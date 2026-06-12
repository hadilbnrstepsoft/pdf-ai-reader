import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import requests
from gtts import gTTS
from langdetect import detect
import json
import pandas as pd
import re
from backend.chat import ask_pdf

st.subheader("🤖 Chat with your PDFs")

question = st.text_input("Ask a question")

if question:
    answer = ask_pdf(question)
    st.write(answer)
# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="PDF AI Reader PRO", layout="wide")

# =========================
# UI SIMPLE
# =========================
st.title("📄 PDF Reader ")

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
    file = "output.mp3"
    tts = gTTS(text=text, lang=lang)
    tts.save(file)
    return file

# =========================
# 🔥 OCR + PDF EXTRACTION (IMPORTANT)
# =========================
def extract_pages(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")

    pages_text = []

    for page in doc:
        text = page.get_text().strip()

        # PDF texte normal
        if len(text) > 20:
            pages_text.append(text)

        # PDF scanné → OCR
        else:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            ocr_text = pytesseract.image_to_string(
                img,
                lang="eng+deu+fra",
                config="--psm 6"
            )

            pages_text.append(ocr_text)

    return pages_text

# =========================
# SPELL MODE
# =========================
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
uploaded_file = st.file_uploader("📤 Upload PDF", type="pdf")

if uploaded_file:

    # RESET FILE POINTER
    uploaded_file.seek(0)

    pages = extract_pages(uploaded_file)
    full_text = " ".join(pages)

    lang = map_lang(detect_language(full_text))

    # =========================
    # INFO
    # =========================
    st.success(f"🌍 Language detected: {lang}")

    # =========================
    # TEXT DISPLAY
    # =========================
    st.text_area("📄 Extracted Text", full_text, height=300)

    # =========================
    # BUTTONS
    # =========================
    col1, col2, col3 = st.columns(3)

    # =========================
    # 🧠 AI EXTRACTION
    # =========================
    with col1:
        if st.button("🧠 Extract JSON Invoice"):

            with st.spinner("AI analyzing..."):

                prompt = f"""
Extract structured JSON from this document.

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

                st.json(data)

                if "articles" in data:
                    df = pd.DataFrame(data["articles"])
                    st.dataframe(df)

    # =========================
    # 🔊 READ
    # =========================
    with col2:
        if st.button("🔊 Read PDF"):

            for i, page in enumerate(pages):
                if page.strip():
                    audio = text_to_speech(page[:2000], lang)
                    st.audio(open(audio, "rb").read())

    # =========================
    # 🔤 SPELL
    # =========================
    with col3:
        if st.button("🔤 Spell PDF"):

            spelled = spell_text(full_text[:1500])
            audio = text_to_speech(spelled, lang)
            st.audio(open(audio, "rb").read())