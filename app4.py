import streamlit as st
import fitz
import requests
import pandas as pd
import json
import re
from gtts import gTTS

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="PDF AI Reader", layout="wide")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(-45deg,#0f172a,#111827,#1e293b,#0f172a);
    background-size: 400% 400%;
    animation: move 12s ease infinite;
    color: white;
}

@keyframes move {
    0% {background-position:0% 50%;}
    50% {background-position:100% 50%;}
    100% {background-position:0% 50%;}
}

.card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.1);
    padding: 18px;
    border-radius: 16px;
    margin-bottom: 12px;
    color: white;
}

h1,h2,h3,h4,p,label {
    color: white !important;
}

textarea {
    background: white !important;
    color: black !important;
    border-radius: 12px !important;
}

[data-testid="stChatInput"] textarea {
    background: white !important;
    color: black !important;
}

[data-testid="stDataFrame"] {
    background: white;
}
[data-testid="stDataFrame"] * {
    color: black !important;
}
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF AI Reader")

# =========================
# STATE
# =========================
if "json_data" not in st.session_state:
    st.session_state.json_data = None

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================
# BACKEND
# =========================
def ask_ollama(prompt):
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )
    return r.json()["response"]

# =========================
# PDF
# =========================
def extract_text(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

# =========================
# SAFE JSON PARSER
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
# PROMPTS (CLEAN ARCHITECTURE)
# =========================

EXTRACTION_PROMPT = """
You are a document extraction system.

Return ONLY valid JSON.

Schema:
{
  "company_name": "",
  "document_type": "",
  "date": "",
  "summary": "",
  "invoice_total": "",
  "articles": [
    {
      "article_number": "",
      "description": "",
      "quantity": "",
      "price": "",
      "total": ""
    }
  ]
}

RULES:
- NO text outside JSON
- NO explanation
- ONLY JSON

TEXT:
"""

CHAT_PROMPT = """
You are a professional PDF assistant.

Rules:
- Answer ONLY using the PDF content
- Be concise
- If not found, say "not found in document"

PDF:
"""

# =========================
# UPLOAD
# =========================
file = st.file_uploader("📤 Upload PDF", type="pdf")

if file:

    st.session_state.pdf_text = extract_text(file)
    text = st.session_state.pdf_text

    col1, col2 = st.columns(2)

    # =========================
    # EXTRACTION MODE
    # =========================
    with col1:
        if st.button("🧠 Extract Data (JSON)"):

            prompt = EXTRACTION_PROMPT + text

            result = ask_ollama(prompt)

            st.session_state.json_data = parse_json(result)

    # =========================
    # PDF TEXT
    # =========================
    with col2:
        st.text_area("📄 PDF TEXT", text, height=250)

# =========================
# STRUCTURED DISPLAY
# =========================
if st.session_state.json_data:

    data = st.session_state.json_data

    st.subheader("📦 Structured Data")

    st.markdown(f"""
    <div class="card">
        <h4>Company</h4>
        <p>{data.get("company_name","")}</p>

        <h4>Summary</h4>
        <p>{data.get("summary","")}</p>

        <h4>Type</h4>
        <p>{data.get("document_type","")}</p>

        <h4>Date</h4>
        <p>{data.get("date","")}</p>

        <h4>Total</h4>
        <p><b>{data.get("invoice_total","")}</b></p>
    </div>
    """, unsafe_allow_html=True)

    if "articles" in data:

        st.subheader("📦 Articles")

        df = pd.DataFrame(data["articles"])

        for i, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <b>Article {i+1}</b><br><br>
                {row.get('description','')}<br>
                Qty: {row.get('quantity','')}<br>
                Price: {row.get('price','')}<br>
                Total: <b>{row.get('total','')}</b>
            </div>
            """, unsafe_allow_html=True)

        st.dataframe(df, use_container_width=True)

# =========================
# CHAT (FIXED CLEAN MODE)
# =========================
st.divider()
st.subheader("💬 Assistant")

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])

q = st.chat_input("Ask your PDF...")

if q:

    st.session_state.chat.append({"role": "user", "content": q})

    prompt = CHAT_PROMPT + st.session_state.pdf_text + "\n\nQUESTION:\n" + q

    answer = ask_ollama(prompt)

    st.session_state.chat.append({"role": "assistant", "content": answer})

    st.rerun()