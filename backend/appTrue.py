import streamlit as st
import fitz
import requests
import pandas as pd
import json
import re
from db import init_db, get_connection
from auth import login_user, register_user
from chat import chat_with_pdf
# =========================
# INIT DB
# =========================
init_db()

# =========================
# SESSION STATE
# =========================
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "json_data" not in st.session_state:
    st.session_state.json_data = None

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="PDF AI SaaS", layout="wide")

# =========================
# DB FUNCTION
# =========================
def get_documents(user_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT id, filename, json_data
        FROM pdf_history
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))

    rows = c.fetchall()
    conn.close()
    return rows

# =========================
# STYLE
# =========================
# =========================
# PREMIUM UI / STEPSOFT STYLE
# =========================
st.markdown("""
<style>

/* ===== MAIN BACKGROUND ===== */

.stApp {
    background:
    linear-gradient(rgba(5,10,25,0.88), rgba(5,10,25,0.92)),
    url("https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2070&auto=format&fit=crop");
    
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: white;
}

/* ===== GLOBAL TEXT ===== */

h1,h2,h3,h4,h5,p,label,span {
    color: white !important;
}

/* ===== GLASS EFFECT ===== */

.block-container {
    padding-top: 2rem;
}

/* ===== INPUTS ===== */

textarea,
input {
    background: rgba(255,255,255,0.95) !important;
    color: black !important;
    border-radius: 14px !important;
}

/* ===== CHAT ===== */

[data-testid="stChatInput"] textarea {
    background: white !important;
    color: black !important;
    border-radius: 14px !important;
}

/* ===== DATAFRAME ===== */

[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.95);
    border-radius: 15px;
    overflow: hidden;
}

[data-testid="stDataFrame"] * {
    color: black !important;
}

/* ===== PDF CARD ===== */

.pdf-card {
    background: rgba(255,255,255,0.08);
    backdrop-filter: blur(14px);

    border: 1px solid rgba(255,255,255,0.12);

    border-radius: 24px;

    padding: 28px;

    margin-top: 20px;
    margin-bottom: 20px;

    box-shadow:
    0 8px 32px rgba(0,0,0,0.35);

    transition: 0.3s;
}

.pdf-card:hover {
    transform: translateY(-4px);
}

/* ===== ROW ===== */

.info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;

    padding: 16px 0;

    border-bottom: 1px solid rgba(255,255,255,0.08);
}

/* ===== LABEL ===== */

.info-label {
    font-size: 16px;
    font-weight: 600;
    color: #94a3b8 !important;
}

/* ===== VALUE ===== */

.info-value {
    font-size: 18px;
    font-weight: 700;
    text-align: right;
}

/* ===== TOTAL ===== */

.total-box {
    margin-top: 20px;

    background: linear-gradient(90deg,#2563eb,#06b6d4);

    border-radius: 18px;

    padding: 18px;

    text-align: center;

    font-size: 28px;
    font-weight: bold;

    box-shadow: 0 6px 20px rgba(37,99,235,0.4);
}

/* ===== BUTTONS ===== */

.stButton button {
    background: linear-gradient(90deg,#2563eb,#0ea5e9);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px 22px;
    font-weight: bold;
    transition: 0.3s;
}

.stButton button:hover {
    transform: scale(1.03);
}

/* ===== SIDEBAR ===== */

section[data-testid="stSidebar"] {
    background: rgba(15,23,42,0.88);
    backdrop-filter: blur(10px);
}

</style>
""", unsafe_allow_html=True)

st.title("📄 PDF Reader")

# =========================================================
# AUTH SYSTEM
# =========================================================
if st.session_state.user_id is None:

    st.subheader("🔐 Login / Register")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            user_id = login_user(u, p)
            if user_id:
                st.session_state.user_id = user_id
                st.success("Logged in successfully")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        u2 = st.text_input("New username")
        p2 = st.text_input("New password", type="password")

        if st.button("Register"):
            if register_user(u2, p2):
                st.success("Account created")
            else:
                st.error("User already exists")

    st.stop()

# =========================================================
# BACKEND AI
# =========================================================
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

# =========================================================
# PDF EXTRACTION
# =========================================================
def extract_text(file):
    if file is None:
        return ""

    doc = fitz.open(stream=file.read(), filetype="pdf")

    text = []
    for page in doc:
        blocks = page.get_text("blocks")

        for b in blocks:
            txt = b[4].strip()
            if txt:
                text.append(txt)

    return "\n".join(text)
def extract_currencies(text):
    currencies = []

    pattern = re.compile(
        r"(\d+)\s+([A-Z]{3})\s+(.+?)\s+([0-9,]+)\s+([0-9,]+)"
    )

    for line in text.splitlines():
        match = pattern.search(line)

        if match:
            currencies.append({
                "WNR": match.group(1),
                "ISO": match.group(2),
                "Waehrung": match.group(3).strip(),
                "Ankauf": match.group(4),
                "Verkauf": match.group(5)
            })

    return currencies

# =========================================================
# JSON PARSER
# =========================================================
def parse_json(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

    return {
        "company_name": "",
        "document_type": "",
        "date": "",
        "summary": "",
        "invoice_total": "",
        "articles": []
    }

# =========================================================
# SAVE PDF
# =========================================================
def save_pdf(user_id, filename, data):
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        INSERT INTO pdf_history (user_id, filename, json_data)
        VALUES (?, ?, ?)
    """, (user_id, filename, json.dumps(data)))

    conn.commit()
    conn.close()

# =========================================================
# UPLOAD
# =========================================================
file = st.file_uploader("📤 Upload PDF", type="pdf")

if file:

    st.session_state.pdf_text = extract_text(file)
    text = st.session_state.pdf_text
    currencies = extract_currencies(text)
    if currencies:

        st.subheader("💱 Wechselkurse")

        df_currency = pd.DataFrame(currencies)

        st.dataframe(
        df_currency,
        use_container_width=True
        )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🧠 Extract JSON"):

            EXTRACTION_PROMPT = """
You are an expert invoice extraction AI.

RULES:
- Output ONLY valid JSON
- No markdown
- No explanations
- Preserve original language
- Detect invoice date carefully
- Extract exact total amount
- Create a short summary of the document
- If missing value use ""

SCHEMA:
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

DOCUMENT:
"""

            result = ask_ollama(EXTRACTION_PROMPT + text)

            st.subheader("RAW LLM RESPONSE")
            st.code(result)

            data = parse_json(result)

            st.session_state.json_data = data

            save_pdf(
                st.session_state.user_id,
                file.name,
                data
            )

            st.success("Saved to database ✔")

    
    with col2:
        st.write("Nombre de caractères :", len(text))
        st.text_area("📄 PDF TEXT", text, height=500)

# =========================================================
# STRUCTURED DATA
# =========================================================
if st.session_state.json_data:

    data = st.session_state.json_data

    st.subheader("📦 Extracted Data")

    st.markdown(f"""
<div class="pdf-card">

    <div class="info-row">
        <div class="info-label">🏢 Company</div>
        <div class="info-value">{data.get("company_name","")}</div>
    </div>

    <div class="info-row">
        <div class="info-label">📝 Summary</div>
        <div class="info-value">{data.get("summary","")}</div>
    </div>

    <div class="info-row">
        <div class="info-label">📄 Type</div>
        <div class="info-value">{data.get("document_type","")}</div>
    </div>

    <div class="info-row">
        <div class="info-label">📅 Date</div>
        <div class="info-value">{data.get("date","")}</div>
    </div>

    <div class="total-box">
        💰 Total : {data.get("invoice_total","")}
    </div>

</div>
""", unsafe_allow_html=True)

# =========================================================
# ARTICLES
# =========================================================
    if isinstance(data.get("articles"), list):

        df = pd.DataFrame(data["articles"])

        st.subheader("📦 Articles")

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

# =========================================================
# HISTORY
# =========================================================
if st.session_state.user_id:

    st.divider()
    st.subheader("📚 My PDF History")

    history = get_documents(st.session_state.user_id)

    for doc_id, filename, data in history:
        st.markdown(f"""
        <div class="card">
            <b>{filename}</b><br>
            <small>{str(data)[:200]}...</small>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# CHAT
# =========================================================
st.divider()
st.subheader("💬 AI Assistant")

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])

q = st.chat_input("Ask your PDF...")

if q:

    st.session_state.chat.append({"role": "user", "content": q})

    answer = chat_with_pdf(
        question=q,
        pdf_text=st.session_state.pdf_text,
        json_data=json.dumps(st.session_state.json_data)
        if st.session_state.json_data else "{}"
    )

    # FIX si dict retourné
    if isinstance(answer, dict):
        answer = answer.get("answer", str(answer))

    st.session_state.chat.append({"role": "assistant", "content": answer})

    st.rerun()