import streamlit as st
import fitz
from openai import OpenAI
import requests

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

client = OpenAI(api_key="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")

st.title("📄 PDF Reader AI (Step 2)")

uploaded_file = st.file_uploader("Upload un fichier PDF", type="pdf")

def extract_text(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

if uploaded_file:
    text = extract_text(uploaded_file)

    st.subheader("📃 Texte extrait")
    st.text_area("Résultat", text, height=300)

    if st.button("🧠 Générer JSON"):
        with st.spinner("Analyse en cours..."):

            prompt = f"""
Analyse ce document et retourne un JSON structuré avec :
- nom
- type_document
- date
- score (si existant)

Texte:
{text}
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Tu es un assistant utile."},
                    {"role": "user", "content": prompt}
                ]
            )

            result = response.choices[0].message.content

            st.subheader("📦 JSON généré")
            st.write(result)