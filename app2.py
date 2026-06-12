import streamlit as st
import fitz  # PyMuPDF
import requests
from gtts import gTTS

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="PDF AI Reader", layout="wide")
st.title("📄 PDF Reader ")

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
# TEXT TO SPEECH
# =========================
def text_to_speech(text):
    tts = gTTS(text=text, lang="fr")
    audio_file = "output.mp3"
    tts.save(audio_file)
    return audio_file

# =========================
# PDF TEXT EXTRACTION
# =========================
def extract_text(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# =========================
# UI
# =========================
uploaded_file = st.file_uploader("📤 Upload PDF", type="pdf")

if uploaded_file:

    # Extract text
    text = extract_text(uploaded_file)

    st.subheader("📃 Texte extrait")
    st.text_area("Contenu PDF", text, height=300)

    # =========================
    # BUTTON: ANALYZE WITH AI
    # =========================
    if st.button("🧠 Analyser avec Ollama (JSON)"):
        with st.spinner("Analyse en cours..."):

            prompt = f"""
Analyse ce document et retourne un JSON structuré avec :
- nom
- type_document
- date (si disponible)
- résumé court

Texte:
{text}
"""

            result = ask_ollama(prompt)

            st.subheader("📦 Résultat IA")
            st.write(result)

    # =========================
    # BUTTON: AUDIO READING
    # =========================
    if st.button("🔊 Lire le PDF"):
        with st.spinner("Génération audio..."):

            short_text = text[:3000]  # éviter overload TTS
            audio_file = text_to_speech(short_text)

            audio_bytes = open(audio_file, "rb").read()
            st.audio(audio_bytes, format="audio/mp3")

            st.success("Lecture prête ✔")