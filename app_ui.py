import streamlit as st
import fitz
import requests
from gtts import gTTS
import json
import pandas as pd
import re

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="PDF AI SaaS PRO",
    layout="wide",
    page_icon="📄"
)

# =========================
# UI STYLE FIX (READABLE)
# =========================
st.markdown("""
<style>

/* BACKGROUND IMAGE */
.stApp {
    background: url("https://images.unsplash.com/photo-1521737604893-d14cc237f11d");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

/* DARK OVERLAY */
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(0,0,0,0.45);
    z-index: 0;
}

/* CONTENT ABOVE */
.main .block-container {
    position: relative;
    z-index: 1;
}

/* =========================
GLOBAL TEXT
========================= */
h1,h2,h3,h4,p,label {
    color: white !important;
}

/* =========================
CARD (GLASS DARK)
========================= */
.card {
    background: rgba(255,255,255,0.10);
    backdrop-filter: blur(12px);
    padding: 16px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 12px;
    color: white;
}

/* =========================
DATAFRAME
========================= */
[data-testid="stDataFrame"] {
    background: white;
    color: black;
}
[data-testid="stDataFrame"] * {
    color: black !important;
}

/* =========================
TEXT AREA (IMPORTANT FIX)
========================= */
textarea {
    background: white !important;
    color: black !important;
    border-radius: 10px !important;
}

/* =========================
CHAT INPUT FIX (IMPORTANT)
========================= */
[data-testid="stChatInput"] textarea {
    background: white !important;
    color: black !important;
    font-weight: 500;
}

/* CHAT MESSAGES */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 10px;
}

</style>
""", unsafe_allow_html=True)

# =========================
# STATE
# =========================
if "json_data" not in st.session_state:
    st.session_state.json_data = None

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =========================
# BACKEND
# =========================
def ask_ollama(prompt):
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        return r.json()["response"]
    except Exception as e:
        return f"Error: {e}"

# =========================
# PDF
# =========================
def extract_text(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

# =========================
# JSON PARSER SAFE
# =========================
def parse_json(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                return {}
    return {}

# =========================
# TITLE
# =========================
st.title("📄 PDF AI SaaS PRO")

# =========================
# UPLOAD
# =========================
file = st.file_uploader("📤 Upload PDF", type="pdf")

if file:

    st.session_state.pdf_text = extract_text(file)
    text = st.session_state.pdf_text

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🧠 Extract JSON"):
            prompt = f"""
Return ONLY valid JSON:

{{
  "company_name": "",
  "document_type": "",
  "date": "",
  "summary": "",
  "invoice_total": "",
  "articles": [
    {{
      "article_number": "",
      "description": "",
      "quantity": "",
      "price": "",
      "total": ""
    }}
  ]
}}

TEXT:
{text}
"""
            res = ask_ollama(prompt)
            st.session_state.json_data = parse_json(res)

    with col2:
        st.text_area("📄 PDF TEXT", text, height=250)

# =========================
# JSON CARDS ONLY
# =========================
if st.session_state.json_data:

    data = st.session_state.json_data

    st.subheader("📦 Company Info")

    for k in ["company_name", "document_type", "date", "summary", "invoice_total"]:
        if k in data:
            st.markdown(f"""
            <div class="card">
                <b>{k}</b><br><br>
                {data[k]}
            </div>
            """, unsafe_allow_html=True)

    # ARTICLES
    if "articles" in data and data["articles"]:

        st.subheader("📦 Articles")

        df = pd.DataFrame(data["articles"])

        for i, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <b>Article {i+1}</b><br><br>
                {row.get('article_number','')}<br>
                {row.get('description','')}<br>
                Qty: {row.get('quantity','')}<br>
                Price: {row.get('price','')} €<br>
                <b>Total: {row.get('total','')}</b>
            </div>
            """, unsafe_allow_html=True)

        st.dataframe(df, use_container_width=True)

# =========================
# CHAT
# =========================
st.divider()
st.subheader("💬 AI Assistant")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

q = st.chat_input("Ask your PDF...")

if q:

    st.session_state.chat_history.append({"role": "user", "content": q})

    prompt = f"""
You are a PDF assistant.

PDF:
{st.session_state.pdf_text}

DATA:
{st.session_state.json_data}

QUESTION:
{q}

Answer clearly.
"""

    answer = ask_ollama(prompt)

    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    st.rerun()