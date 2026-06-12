import streamlit as st
import fitz
import requests
import pandas as pd
import json
import re
import sqlite3
import os
from datetime import datetime

# =========================
# DATABASE SETUP (tout-en-un)
# =========================
DB_PATH = "saas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        json_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

def register_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def login_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_documents(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, filename, json_data FROM pdf_history WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_pdf(user_id, filename, data):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO pdf_history (user_id, filename, json_data) VALUES (?, ?, ?)",
              (user_id, filename, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

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
# FONCTIONS D'EXTRACTION PDF
# =========================
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
    pattern = re.compile(r"(\d+)\s+([A-Z]{3})\s+(.+?)\s+([0-9,]+)\s+([0-9,]+)")
    currencies = []
    for line in text.splitlines():
        m = pattern.search(line)
        if m:
            currencies.append({
                "WNR": m.group(1),
                "ISO": m.group(2),
                "Waehrung": m.group(3).strip(),
                "Ankauf": m.group(4),
                "Verkauf": m.group(5)
            })
    return currencies

def parse_json(raw):
    try:
        return json.loads(raw)
    except:
        match = re.search(r"\{[\s\S]*\}", raw)
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

# =========================
# APPEL À L'IA (Hugging Face)
# =========================
def ask_huggingface(prompt, model="mistralai/Mistral-7B-Instruct-v0.3"):
    token = st.secrets.get("HF_TOKEN")
    if not token:
        st.error("❌ HF_TOKEN manquant dans les secrets. L'extraction JSON est désactivée.")
        return "{}"
    
    API_URL = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.2,
            "return_full_text": False
        }
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "{}")
        elif isinstance(result, dict):
            return result.get("generated_text", "{}")
        else:
            return "{}"
    except Exception as e:
        st.error(f"Erreur API : {e}")
        return "{}"

# =========================
# CHAT AVEC IA
# =========================
def chat_with_pdf(question, pdf_text, json_data):
    prompt = f"""
Tu es un assistant expert en analyse de documents PDF.
Voici le texte extrait du PDF :
{pdf_text[:3000]}

Voici les données structurées extraites :
{json_data}

Question : {question}
Réponds de manière claire et concise en te basant uniquement sur le document.
"""
    return ask_huggingface(prompt)

# =========================
# FALLBACK EXTRACTION ARTICLES PAR REGEX (si l'IA échoue)
# =========================
def extract_articles_regex(text):
    """
    Extrait les articles à partir du tableau présent dans le PDF.
    Exemple de ligne : "1  MA0R00004  10.000,0 kg  1,29  12.900,00  LDPE 150 E natur"
    """
    articles = []
    lines = text.splitlines()
    # Pattern pour capturer les lignes d'article
    pattern = re.compile(r'^\d+\s+(\S+)\s+([\d\.,]+\s*kg)\s+([\d\.,]+)\s+([\d\.,]+)\s+(.+)$', re.IGNORECASE)
    for line in lines:
        m = pattern.match(line.strip())
        if m:
            articles.append({
                "article_number": m.group(1),
                "description": m.group(5).strip(),
                "quantity": m.group(2).replace('kg', '').strip(),
                "price": m.group(3).replace(',', '.'),
                "total": m.group(4).replace(',', '.')
            })
    return articles

# =========================
# UI
# =========================
st.set_page_config(page_title="PDF AI SaaS", layout="wide")
st.markdown("""
<style>
.stApp { background: linear-gradient(rgba(5,10,25,0.88), rgba(5,10,25,0.92)), url("https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2070&auto=format&fit=crop"); background-size: cover; background-position: center; background-attachment: fixed; color: white; }
h1,h2,h3,h4,h5,p,label,span { color: white !important; }
.block-container { padding-top: 2rem; }
textarea, input { background: rgba(255,255,255,0.95) !important; color: black !important; border-radius: 14px !important; }
[data-testid="stDataFrame"] { background: rgba(255,255,255,0.95); border-radius: 15px; overflow: hidden; }
[data-testid="stDataFrame"] * { color: black !important; }
.pdf-card { background: rgba(255,255,255,0.08); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.12); border-radius: 24px; padding: 28px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.35); transition: 0.3s; }
.pdf-card:hover { transform: translateY(-4px); }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
.info-label { font-size: 16px; font-weight: 600; color: #94a3b8 !important; }
.info-value { font-size: 18px; font-weight: 700; text-align: right; }
.total-box { margin-top: 20px; background: linear-gradient(90deg,#2563eb,#06b6d4); border-radius: 18px; padding: 18px; text-align: center; font-size: 28px; font-weight: bold; box-shadow: 0 6px 20px rgba(37,99,235,0.4); }
.stButton button { background: linear-gradient(90deg,#2563eb,#0ea5e9); color: white; border: none; border-radius: 14px; padding: 12px 22px; font-weight: bold; transition: 0.3s; }
.stButton button:hover { transform: scale(1.03); }
section[data-testid="stSidebar"] { background: rgba(15,23,42,0.88); backdrop-filter: blur(10px); }
.card { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 12px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF AI SaaS - Test Client")

# =========================
# AUTH
# =========================
if st.session_state.user_id is None:
    st.subheader("🔐 Login / Register")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            uid = login_user(u, p)
            if uid:
                st.session_state.user_id = uid
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

st.sidebar.success(f"Connecté (ID {st.session_state.user_id})")
if st.sidebar.button("Déconnexion"):
    st.session_state.user_id = None
    st.session_state.json_data = None
    st.session_state.pdf_text = ""
    st.session_state.chat = []
    st.rerun()

# =========================
# UPLOAD PDF
# =========================
file = st.file_uploader("📤 Upload PDF", type=["pdf"])

if file:
    # Extraction du texte
    st.session_state.pdf_text = extract_text(file)
    text = st.session_state.pdf_text
    st.success(f"Texte extrait : {len(text)} caractères")

    # Devises
    currencies = extract_currencies(text)
    if currencies:
        st.subheader("💱 Wechselkurse")
        st.dataframe(pd.DataFrame(currencies), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧠 Extract JSON"):
            extraction_prompt = """
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
            with st.spinner("Appel à l'IA..."):
                result = ask_huggingface(extraction_prompt + text)
            st.subheader("RAW LLM RESPONSE")
            st.code(result)
            data = parse_json(result)
            # Si l'IA n'a rien extrait, on utilise le fallback regex
            if not data.get("articles"):
                fallback_articles = extract_articles_regex(text)
                if fallback_articles:
                    data["articles"] = fallback_articles
                    st.info("Utilisation de l'extraction par regex (fallback) car l'IA n'a pas retourné d'articles.")
            st.session_state.json_data = data
            save_pdf(st.session_state.user_id, file.name, data)
            st.success("Saved to database ✔")

    with col2:
        st.write("Nombre de caractères :", len(text))
        st.text_area("📄 PDF TEXT", text, height=500)

# =========================
# STRUCTURED DATA
# =========================
if st.session_state.json_data:
    data = st.session_state.json_data
    st.subheader("📦 Extracted Data")
    st.markdown(f"""
<div class="pdf-card">
    <div class="info-row"><div class="info-label">🏢 Company</div><div class="info-value">{data.get("company_name","")}</div></div>
    <div class="info-row"><div class="info-label">📝 Summary</div><div class="info-value">{data.get("summary","")}</div></div>
    <div class="info-row"><div class="info-label">📄 Type</div><div class="info-value">{data.get("document_type","")}</div></div>
    <div class="info-row"><div class="info-label">📅 Date</div><div class="info-value">{data.get("date","")}</div></div>
    <div class="total-box">💰 Total : {data.get("invoice_total","")}</div>
</div>
""", unsafe_allow_html=True)

    if isinstance(data.get("articles"), list) and data["articles"]:
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
    else:
        st.info("Aucun article détecté.")

# =========================
# HISTORY
# =========================
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

# =========================
# CHAT
# =========================
st.divider()
st.subheader("💬 AI Assistant")
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])

q = st.chat_input("Ask your PDF...")
if q:
    st.session_state.chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        with st.spinner("Réflexion..."):
            answer = chat_with_pdf(
                q,
                st.session_state.pdf_text,
                json.dumps(st.session_state.json_data) if st.session_state.json_data else "{}"
            )
            st.write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer})
    st.rerun()